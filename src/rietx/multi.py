"""The joint call's module before v1.13, kept only to name its replacement.

WP-2305 renamed ``rietx.multi`` to :mod:`rietx.joint`, ``refine_multi`` to
``refine_joint`` and ``MultiHistogramRefinement`` to ``JointRefinement``.  An
import of this module raises ``ModuleNotFoundError`` naming them, so a script
written against an older release learns the new names at its first line.  The
error is that subclass, with ``name`` set to this module, so
``rietx.__getattr__`` reads ``rietx.multi`` as a missing submodule and answers
it from ``_TOP_LEVEL_HINTS`` as an ``AttributeError``.
"""

raise ModuleNotFoundError(
    "rietx.multi was renamed in v1.13: import rietx.joint, and call "
    "refine_joint / JointRefinement (formerly refine_multi / "
    "MultiHistogramRefinement)", name=__name__)
