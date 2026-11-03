"""Cooperative cancellation of a running refinement.

A fit is a python loop calling numpy; there is no safe way to interrupt one
from outside, and there is no need for one.  :class:`CancelToken` is a flag the
caller sets from another thread (the GUI server holds one per session and POST
``/api/cancel`` sets it), and the solver reads it **at eval boundaries** — in
between two residual evaluations, where the compiled model is quiescent.  That
is what keeps frozen-per-stage discreteness intact: nothing reaches into the
compiled state, and the stage simply stops being asked for more evaluations.

The token is deliberately dumb — set it, read it — so that mapping an HTTP
route onto it is one line and no lifecycle can go wrong.  Everything about
*what a cancelled run leaves behind* lives on the exception instead:

* the in-flight stage is **abandoned** — no history node, the parameter table
  is not committed, and the structure/instrument are restored to their
  pre-stage values (a stage that seeds — extinction's floor lift, the
  Stephens isotropic ray — writes to the models before solving, and leaving
  that seed behind would be a stage that half-ran);
* :attr:`RefinementCancelled.completed_stages` and
  :attr:`RefinementCancelled.node_id` say where the working state *does* stand:
  at the last completed node, which is exactly a checkout target.

Timeouts and watchdogs are not here on purpose: they compose from the token
(``threading.Timer(30, token.cancel)``) and each caller wants a different
policy.
"""

from __future__ import annotations

import threading
from typing import Any


class CancelToken:
    """A thread-safe "stop asking for evaluations" flag.

    Wraps :class:`threading.Event` rather than a bare bool because the setter
    and the reader are genuinely on different threads in the GUI.
    """

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation; returns immediately (nothing blocks on this)."""
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    def reset(self) -> None:
        """Clear the flag so the token can be reused for the next run."""
        self._event.clear()

    def __bool__(self) -> bool:
        return self._event.is_set()

    def __repr__(self) -> str:
        return f"CancelToken(cancelled={self._event.is_set()})"


class RefinementCancelled(Exception):
    """Raised out of a fit whose :class:`CancelToken` was set.

    Attributes
    ----------
    stage:
        Name of the abandoned stage — the one that was in flight.
    completed_stages:
        ``list[StageResult]`` for the stages that finished before it.  Empty
        when the first stage was cancelled.
    node_id:
        History node holding the working state, i.e. the last completed stage
        (``None`` with history disabled, or when nothing completed).
    """

    def __init__(self, message: str = "refinement cancelled", *,
                 stage: str = "", completed_stages: list[Any] | None = None,
                 node_id: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.completed_stages: list[Any] = list(completed_stages or [])
        self.node_id = node_id
