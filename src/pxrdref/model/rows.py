"""The residual row layout — the single authority every path builds from.

Why this module exists
----------------------
The least-squares residual is not just the data: it is

    [ data | background-penalty | Pawley-restraint | soft-restraint ]

and until this module existed that ordering was written out **four** times —
the numpy residual closure, the numpy Jacobian's row offsets, and the jax and
torch traced residuals.  WP-0406 flagged the duplication as a hazard and
WP-0408 hit it for real: the soft-restraint rows shipped in three of those
places and had to be retro-fitted to the fourth when the branches were
integrated.  A fifth backend, or a fifth block, would have had the same
problem, and a *test* cannot prevent it — a test can only notice afterwards,
and only for a block some test already exercises.

So the layout is data here, and the builders are consumers:

* :func:`block_sizes` / :func:`layout` / :func:`n_rows` answer "how many rows,
  and where does each block start" — used by the Jacobian, which writes into
  row slices, and by anything that needs to split a residual back apart;
* :func:`assemble` builds the residual itself from :data:`BLOCK_ORDER`, for
  every backend, so the numpy and traced paths cannot order their blocks
  differently.

**Adding a row block is one edit here** — a name in :data:`BLOCK_ORDER`, a
size in :func:`block_sizes`, a producer in :data:`_PRODUCERS` — and every
backend and the Jacobian offsets follow.  ``tests/test_row_layout.py`` asserts
the three stay in step and that no builder re-derives the order locally.

Conventions this module has to honour (CLAUDE.md → Conventions):

* the caller supplies ``sqrt_w`` and ``y_obs`` **already lifted onto its own
  backend**, because a frozen numpy constant on the left of an operator
  against a traced value raises on torch and mis-routes under functorch;
* the blocks are frozen per stage, like everything else discrete: sizes come
  from compiled state, never from θ.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: Row blocks, in the order they are stacked below the data.  This tuple *is*
#: the layout — read it, never restate it.
BLOCK_ORDER: tuple[str, ...] = (
    "data",
    "background_penalty",
    "pawley_restraint",
    "soft_restraint",
)


@dataclass(frozen=True)
class RowBlock:
    """One block's extent in the assembled residual (empty blocks included)."""

    name: str
    start: int
    stop: int

    @property
    def n(self) -> int:
        return self.stop - self.start

    @property
    def rows(self) -> slice:
        return slice(self.start, self.stop)


def block_sizes(model) -> dict[str, int]:
    """Row count per block for this compiled model, keyed by :data:`BLOCK_ORDER`.

    Every block appears, including the ones this model does not have (0 rows),
    so callers can index by name without knowing which features are active.
    """
    return {
        "data": len(model.tt),
        "background_penalty": (0 if model.bkg_penalty is None
                               else model.bkg_penalty.shape[0]),
        "pawley_restraint": (0 if model.pawley is None
                             or model.pawley.restraint is None
                             else model.pawley.restraint.shape[0]),
        "soft_restraint": (0 if model.restraints is None
                           else model.restraints.n_rows),
    }


def layout(model) -> tuple[RowBlock, ...]:
    """The blocks with their cumulative offsets, in :data:`BLOCK_ORDER`."""
    sizes = block_sizes(model)
    out, start = [], 0
    for name in BLOCK_ORDER:
        stop = start + sizes[name]
        out.append(RowBlock(name, start, stop))
        start = stop
    return tuple(out)


def block(model, name: str) -> RowBlock:
    """One named block's extent — ``layout(model)`` indexed by name."""
    for b in layout(model):
        if b.name == name:
            return b
    raise KeyError(f"unknown row block {name!r}; known: {BLOCK_ORDER}")


def n_rows(model) -> int:
    """Total residual length: data rows plus every penalty/restraint block."""
    return sum(block_sizes(model).values())


# ----------------------------------------------------------------------
# assembly
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ResidualInputs:
    """Everything a block producer may read.

    ``sqrt_w`` and ``y_obs`` arrive lifted onto ``xp`` by the caller (see the
    module docstring); ``theta_aux`` is the off-table Pawley intensity vector,
    empty for every other mode.
    """

    values: dict[str, Any]
    intens: Any
    theta_aux: Any
    sqrt_w: Any
    y_obs: Any
    xp: Any


def _data_rows(model, ctx: ResidualInputs):
    return ctx.sqrt_w * (ctx.y_obs - model.evaluate(ctx.values, ctx.intens))


def _background_penalty_rows(model, ctx: ResidualInputs):
    return model.penalty_residual(ctx.values)


def _pawley_restraint_rows(model, ctx: ResidualInputs):
    if model.pawley is None:
        return None
    return model.pawley_restraint_residual(ctx.theta_aux)


def _soft_restraint_rows(model, ctx: ResidualInputs):
    return model.restraint_residual(ctx.values)


#: name → producer, returning that block's rows or ``None`` when it has none.
#: Keys must match :data:`BLOCK_ORDER` exactly (asserted below and in tests).
_PRODUCERS = {
    "data": _data_rows,
    "background_penalty": _background_penalty_rows,
    "pawley_restraint": _pawley_restraint_rows,
    "soft_restraint": _soft_restraint_rows,
}

assert tuple(_PRODUCERS) == BLOCK_ORDER, "producers must cover BLOCK_ORDER in order"


def assemble(model, ctx: ResidualInputs):
    """The full residual, blocks stacked in :data:`BLOCK_ORDER`.

    Backend-agnostic: it calls ``ctx.xp.concatenate`` and the model's own row
    producers, all of which are already written against the op shim.  A single
    block is returned unconcatenated, exactly as the per-backend closures did
    before they were collapsed here, so the numpy path keeps its zero-copy
    fast case.
    """
    parts = []
    for name in BLOCK_ORDER:
        rows = _PRODUCERS[name](model, ctx)
        if rows is not None:
            parts.append(rows)
    return parts[0] if len(parts) == 1 else ctx.xp.concatenate(parts)
