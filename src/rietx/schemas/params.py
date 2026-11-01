"""The parameter table as data: one row per refinable scalar.

``params.vector.Entry`` is the ground truth of what a parameter *is* — path,
value, vary flag, bounds, affine tie, locked flag — but it is a
dataclass inside the optimiser's translation layer, and the hot loop is
deliberately free of pydantic.  :class:`ParameterRow` is its serializable twin
for the cold paths: a listing for a caller (``Refinement.parameters()``), a GUI
parameter table (WP-1011), a text document (WP-1009).

Unlike :class:`~rietx.schemas.results.RefinedParameter`, which reports what a
fit *refined*, a row exists for **every** entry — fixed, locked and tied ones
included.  A caller deciding what to free next has to see the whole table,
including the parts it may not touch and why it may not.  Five separate
reasons make a row un-refinable and they are distinguishable on purpose:

* ``locked`` — structurally fixed, ``set_vary`` can never free it (a
  symmetry-fixed cell angle, the line-0 emission weight, ``biso`` on a site
  that declares an anisotropic tensor);
* ``tie`` — an affine function of other entries, so the freedom lives in its
  sources (``b`` in a tetragonal cell, an atom coordinate behind its Wyckoff
  DOFs);
* ``mode_fixed`` — refinable in principle, but force-fixed by the intensity
  mode currently in force;
* ``held`` — the caller declared it does not move, with ``Refinement.hold``
  (WP-1435), or through ``Phase.floating_origin``, which holds one
  coordinate per floating-origin direction (WP-1912; ``origin_axis`` says
  which).  The only one a caller both created and can lift;
* ``needs_held_cell`` — a wavelength this histogram's free cell makes
  degenerate.  The only *dynamic* one: another parameter's state decides it.

:attr:`ParameterRow.refinable` is the single predicate over the five, so a
front end has one rule to grey a row by rather than five it could get wrong.
:attr:`ParameterRow.held_because` orders them by what the caller can do.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .common import Base


class TieSpec(Base):
    """The JSON form of ``params.vector.AffineTie``, value = Σ c·src + k.

    :attr:`user` separates the two populations that share this shape.  A
    **symmetry** tie is derived: ``ParameterTable`` rebuilds it from the space
    group and the Wyckoff position every time it is constructed, and nothing a
    caller does can remove it.  A **user** tie (WP-1070) is declared through
    ``Refinement.tie``/``tie_equal``, lives in the history, and can be taken
    back with ``untie``.  Both hold a row the same way, so ``held_because``
    reads the same for either; the flag is what lets a client tell a row it may
    release from one it may not, without having to try.
    """

    terms: list[tuple[str, float]] = Field(default_factory=list)
    const: float = 0.0
    user: bool = False

    @classmethod
    def _from_tie(cls, tie: Any, *, user: bool = False) -> "TieSpec":
        """Convert a :class:`rietx.params.vector.AffineTie` — **internal**.

        Private because its argument is (WP-1076).  ``AffineTie`` is not on the
        public surface and has no reason to be: it is what ``ParameterTable``
        holds, a caller only ever sees the ``TieSpec`` this returns.  As a
        public classmethod it was a converter that could not name what it
        converts, so it sat in the manual's provisional bucket with nothing
        honest to say about it.
        """
        return cls(terms=[(p, float(c)) for p, c in tie.terms], const=float(tie.const),
                   user=user)

    @property
    def sources(self) -> list[str]:
        """The paths this value follows — what to edit instead of this row."""
        return [p for p, _ in self.terms]

    def describe(self) -> str:
        """Human-readable right-hand side, e.g. ``0.1993 + 1·phases.0.atoms.1.dof.0``."""
        parts = [f"{c:g}·{p}" for p, c in self.terms]
        if self.const or not parts:
            parts.insert(0, f"{self.const:g}")
        return " + ".join(parts)


class ParameterRow(Base):
    """One row of the parameter table, mirroring ``params.vector.Entry``.

    ``.value``/``.esd`` are the numbers; the whole table, held rows included,
    comes from ``Refinement.parameters()``, never from re-deriving one here.

    The first eight fields are ``Entry``'s, name for name;
    ``tests/test_params_surface.py`` asserts that against
    ``dataclasses.fields(Entry)`` so a new ``Entry`` field cannot go unexposed.
    The rest are **deliberate additions**, listed in that same test's
    ``DELIBERATE_EXTRAS`` rather than special-cased silently:

    ``esd``
        the standard uncertainty from the most recent fit, if this parameter was
        free or tied in it.  It belongs on the row and not on ``Entry`` because
        ``Entry`` is what the residual reads; an esd is a property of a
        *completed* fit, and merging it here is what lets one listing answer
        "what is this worth, and how well is it known".
    ``mode_fixed``
        ``True`` when ``lebail``/``pawley`` mode force-fixes this path (every
        ``.atoms.`` path, the phase scale, a texture coefficient — see
        ``Refinement._run_stage``).  It is not ``locked``: nothing about the
        parameter is structurally fixed, and switching back to ``rietveld``
        frees it again.  The distinction matters most for a Le Bail-only phase,
        which must carry a dummy atom to exist at all — presenting its
        ``biso`` as editable would invite refining something the mode discards.
    """

    path: str
    value: float
    vary: bool = False
    lo: float = float("-inf")
    hi: float = float("inf")
    tie: TieSpec | None = None
    locked: bool = False
    #: The caller declared that this parameter does not move (WP-1435),
    #: through ``Refinement.hold``.  An ``Entry`` field rather than one of the
    #: extras below, because a hold behaves exactly as ``locked`` does inside
    #: ``ParameterTable.set_vary`` and the table has to carry it to enforce it.
    #:
    #: It is the one held-reason a caller can lift, with ``unhold``.  That is
    #: also what it is *for*: a stage's ``turn_on`` glob frees whatever it
    #: matches, so ``vary=False`` alone survives no plan, and before this a
    #: certified cell pinned for a calibration was refined anyway while the
    #: model still read ``vary=False``.
    held: bool = False
    esd: float | None = None
    mode_fixed: bool = False
    #: A wavelength that cannot be freed **right now** because this histogram's
    #: cell is free, making the two an exactly flat direction.  The fourth
    #: held-reason, and the only *dynamic* one: unlike ``locked`` it is not a
    #: fact about the parameter, and unlike ``mode_fixed`` it is undone by
    #: holding the cell rather than by changing the mode.  It exists because
    #: ``refinable`` promises "``set_vary`` could free this", and with a free
    #: cell ``set_vary`` skips the row — so without this flag the promise would
    #: be false while ``held_because`` said nothing (the defaulted-``False``
    #: failure WP-1076 removes).
    needs_held_cell: bool = False
    #: The rigid body whose map writes this row (WP-1805), or ``None``.  A
    #: body atom's x, y, z are locked like a symmetry-fixed coordinate, and
    #: this says which of the two holds it: the remedy differs (refine the
    #: body's origin and rotation), so ``held_because`` names it first.
    body: str | None = None
    #: The direction this row holds a polar group's floating origin along
    #: (WP-1912), as the integer axis ``wyckoff.floating_origin_basis``
    #: returns, or ``None``.  Set only beside ``held``: the hold is
    #: ``ParameterTable``'s, derived from ``Phase.floating_origin``, so this
    #: says which of the two holds a ``held`` row and ``held_because`` gives
    #: that reason.  Written by ``Refinement.parameters`` from
    #: ``ParameterTable.origin_holds`` for every row, so ``None`` means "not
    #: holding an origin", never "not checked".
    origin_axis: tuple[int, int, int] | None = None
    #: The :data:`rietx.help.PARAMETER_HELP` glob whose entry describes this
    #: path, or ``None`` when no family claims it.  The only extra that is not
    #: a held-reason: it says what the parameter *is*, and it is a key rather
    #: than the entry because an entry describes a family and a table repeats
    #: each one once per atom (``help.help_key_for`` has the measurement).
    #: Filled here rather than by whichever surface displays it, so ``None``
    #: means "no family claims this" for every caller and not "nobody looked" —
    #: the defaulted-answer failure WP-1076 went through the result rows for.
    help_key: str | None = None

    @property
    def refinable(self) -> bool:
        """Whether ``set_vary`` could free this row in the current mode."""
        return (not self.locked and self.tie is None and not self.mode_fixed
                and not self.held and not self.needs_held_cell)

    def __str__(self) -> str:
        """``path  value(esd)  state`` on one line, so a list of rows reads as
        a table (WP-1544)."""
        from .._display import parameter_cells
        return "  ".join(parameter_cells(self))

    @property
    def held_because(self) -> str:
        """Why this row cannot be freed, or ``""`` when it can be.

        Ordered by what a caller can do about it.  The three structural
        reasons come first, because no verb lifts them.  A hold comes next,
        being the caller's own and liftable with ``unhold``; it is reported
        after ``mode_fixed`` so that a Le Bail phase's held atom names the
        mode, which is the reason that would still hold if the hold went.  The
        same rule puts the mode before a body: under Le Bail or Pawley the
        body's origin and rotation are force-fixed too, so "refine them
        instead" would send the caller to a refusal (#801).
        """
        if self.body is not None:
            if self.mode_fixed:
                return "force-fixed by the intensity mode (lebail/pawley)"
            return (f"placed by rigid body {self.body!r}: refine its origin "
                    "and rotation instead")
        if self.locked:
            return "structurally fixed by symmetry or by the model"
        if self.tie is not None:
            return f"tied: = {self.tie.describe()}"
        if self.mode_fixed:
            return "force-fixed by the intensity mode (lebail/pawley)"
        if self.held and self.origin_axis is not None:
            return (f"holds the phase's floating origin along "
                    f"{list(self.origin_axis)}: shifting every atom that way "
                    "changes no intensity, so one coordinate is held "
                    "(Phase.floating_origin); unhold() releases it")
        if self.held:
            return ("held by this refinement: declared with hold(), so no "
                    "stage's turn_on frees it until unhold()")
        if self.needs_held_cell:
            return ("a free wavelength needs this histogram's cell held: "
                    "d = lambda/(2 sin theta) fixes only the product")
        return ""
