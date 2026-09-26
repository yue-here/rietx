"""``Refinement.suggest()`` result schemas and gates (WP-1050).

The contract mirrors ``IndexingResult``: there is **no** ``.best`` attribute,
only a gated :meth:`SuggestionResult.best_or_none` that returns ``None``
whenever the evidence does not pick one parameter.  A set of candidates the
data cannot separate comes back as a single multi-member
:class:`CandidateGroup` with ``resolved=False`` — the tie it is — rather than
as whichever member happened to score highest (Toby, 2024, J. Appl. Cryst.
57, 175 names exactly this failure: "a much larger derivative for an
instrumental broadening term than for sample broadening").

Constants live here beside the models they gate (the ``report/schemas.py``
pattern) so agent behaviour is reproducible from the serialized result alone.
"""

from __future__ import annotations

from pydantic import Field

from .common import Base

#: Noise-floor **multiple**: a candidate is quotable only when its predicted
#: Δχ² exceeds ``SUGGEST_MIN_GAIN · max(χ²_red, 1)``.  Under H₀ (the held
#: parameter's true gain is zero) the Rao score gain is ~χ²₁·χ²_red, and 9.0
#: is the 3σ point of χ²₁ (P[χ²₁ > 9] ≈ 0.0027).  ``max(·, 1)`` is
#: ``normal_covariance``'s ``chi2_floor`` convention one module over: an
#: imperfect model's locally-good χ² must not *deflate* the floor.
#: Calibrated on the layers suite's truth fixture (``tests/test_suggest.py``,
#: WP-1050): at the converged state the largest candidate gain measured is
#: 5.7 at χ²_red 1.011 — the floor of 9.10 clears it by 1.6× — while the
#: smallest injected-single-cause *top* gain in the misfit suite is ≈2.5×10³,
#: so the two sides of this gate sit ~440× apart.
SUGGEST_MIN_GAIN = 9.0

#: R² of a candidate's Jacobian column on the span of the currently-free
#: block above which the candidate is *non-separable*: whatever it would fit
#: is already reachable by parameters that are free, so its gain is not
#: evidence about *it*.  0.95 also caps the ``1/(1−R²)`` factor by which
#: near-collinearity inflates the gain at 20×.
SUGGEST_ABSORPTION_MAX = 0.95

#: Pairwise ρ² between two candidates' *projected* (free-block-removed)
#: columns above which they merge into one :class:`CandidateGroup`: the data
#: cannot tell them apart, so ranking one over the other would be a confident
#: singleton the evidence does not support.  Same union-find threshold role as
#: ``SUGGEST_ABSORPTION_MAX``, one gate over.
SUGGEST_GROUP_R2 = 0.95


class ParameterCandidate(Base):
    """One held-but-refinable parameter, scored at the current state.

    ``gain`` is the Rao-score / Gauss-Newton predicted Δχ² from freeing this
    parameter alone (weighted SSR units, **not** reduced — compare against
    ``SuggestionResult.noise_floor``).  ``gradient`` is ∂χ²/∂p in the
    parameter's physical units, sign included, so a consumer sees which way
    the parameter wants to move.  ``absorption`` is the R² of the candidate's
    column on the span of the currently-free block (0.0 when nothing is
    free).

    ``seeded`` marks a candidate whose stored value sits on a transform floor
    where its column is dead (softplus at 0, a Stephens block at S ≡ 0): the
    score was measured at ``seed_value``, not at the stored value, and an
    assumed probe point must never look like a measured state.

    ``action_kind`` is the FitReport Layer-2 cross-reference: when this
    candidate's path matches a ``SuggestedAction``'s paths, the action's kind
    is recorded — two independent methods agreeing.  It is a plain ``str``
    because ``report`` imports ``schemas``, never the reverse; a meta-test
    pins the values to ``typing.get_args(ActionKind)``.
    """

    path: str
    gain: float
    gradient: float
    absorption: float = 0.0
    seeded: bool = False
    seed_value: float | None = None
    action_kind: str | None = None


class CandidateGroup(Base):
    """One rankable unit: a single candidate, or a tie the data cannot split.

    ``resolved`` is ``False`` exactly when the group has more than one member
    — the pairwise-ρ² union-find merged candidates whose projected columns
    are interchangeable, and ``gain`` is then the *joint* gain of freeing the
    whole group (what the data actually measures; per-member gains are the
    members' own, near-equal by construction).

    ``delta_bic`` is the same gain read as a **model-selection** answer
    (WP-1305).  ``gain`` ranks; it does not say whether the improvement pays
    for the parameter it costs, and at powder-pattern channel counts that is
    the question — the protocol's §4 rule reads the t-ratio first and ΔBIC
    at N/f² beside it (WP-1417), and the ramp run that motivated this field held zero shift and sample
    displacement on a ΔBIC its agent had to measure by hand with two extra
    refits per candidate.  It is :func:`~rietx.report.layer2.delta_bic`
    (Schwarz 1978) — the package's one BIC form — evaluated at the
    Gauss-Newton *prediction* of what freeing this group reaches:
    ``chi2_restricted`` the probe's own weighted SSR, ``chi2_full`` that SSR
    minus :attr:`gain`, ``n_added`` the number of members, and — since #270 —
    N the **effective** count :attr:`SuggestionResult.n_effective`, the probe
    residual's length divided by the square of its own Bérar-Lelann factor
    (:func:`~rietx.optimize.statistics.effective_sample_size`).  Raw N let any
    improvement outvote the ln N penalty on a serially correlated powder
    residual, blessing parameters their own esds put within 1σ of zero; at
    N_eff one parameter's ΔBIC is its predicted t² at the inflated esd minus
    ln N_eff.  :attr:`delta_bic_raw_n` is the raw-N figure, kept beside it.  **Positive favours freeing**, the sign
    layer2 defines, so a full refit's ΔBIC computed the same way — charged at
    ``effective_sample_size`` of the **restricted** fit's ``esd_inflation``,
    since the probe measures f on the restricted state's residual — is
    directly comparable.  :func:`~rietx.report.compare_freed` computes it that
    way from two fitted refinements, and ``test_suggest.py`` pins the two
    against each other.

    Predicted, not measured: the linearisation is the same one ``gain`` is,
    and a group whose predicted ``chi2_full`` reaches zero leaves the linear
    regime entirely, where layer2's own guard returns ``0.0`` — no claim
    rather than an infinite one.

    A positive ``gain`` above the noise floor with ``delta_bic`` at or below
    zero is not a contradiction and is the common case on a long pattern: the
    floor is the 3σ point of χ²₁ (:data:`SUGGEST_MIN_GAIN`) while BIC charges
    ``ln N`` per parameter, ≈ 10 at 22 000 channels.  Read it as "this
    parameter has leverage, and the leverage does not pay for it".
    """

    members: list[ParameterCandidate] = Field(min_length=1)
    gain: float
    resolved: bool
    delta_bic: float
    #: the same ΔBIC at the raw residual row count, the pre-#270 figure: an
    #: upper bound on the evidence, which the serial correlation measured in
    #: :attr:`SuggestionResult.n_effective` says to discount.  ``None`` where
    #: the group was not built by ``suggest`` (written by ``build_suggestion``).
    delta_bic_raw_n: float | None = None


class SuggestionResult(Base):
    """Ranked, gated answer to "which parameter should be freed next?".

    ``groups`` is ranked by descending gain and carries only candidates above
    ``noise_floor`` — a converged fit therefore has an *empty* list, which is
    the correct suggestion.  What did not make the list is reported, not
    dropped: ``non_separable`` holds candidates the absorption gate refused
    (their ``absorption`` says why), ``skipped`` the paths whose columns have
    zero norm at this state (no leverage either way), and ``n_evaluated`` how
    many candidates were scored in total, so "no suggestion" is
    distinguishable from "nothing was looked at".

    ``noise_floor`` is the applied ``SUGGEST_MIN_GAIN · max(chi2_red, 1)``,
    stored so the serialized result explains its own gate.
    """

    groups: list[CandidateGroup] = Field(default_factory=list)
    non_separable: list[ParameterCandidate] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    n_evaluated: int = 0
    chi2_red: float
    noise_floor: float
    summary: str
    #: the observation count every :attr:`CandidateGroup.delta_bic` was
    #: charged at: the probe's residual rows over the square of their
    #: Bérar-Lelann factor (#270).  ``None`` where no factor was measured, in
    #: which case the groups' ΔBIC is at the raw count.
    n_effective: float | None = None

    def best_or_none(self) -> ParameterCandidate | None:
        """The one defensible winner, or ``None``.

        ``None`` whenever there is nothing above the noise floor, or the top
        group is an unresolved tie — never a confident singleton the gates
        cannot defend.  A caller who wants the full evidence reads
        ``groups`` directly.
        """
        if not self.groups or not self.groups[0].resolved:
            return None
        return self.groups[0].members[0]
