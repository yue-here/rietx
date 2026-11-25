"""Shim tracer for the agent-surface round (WP-1110 round 1.0; WP-1307 round 1.1).

Installed into the *experiment* venv's site-packages (never into the package
under test) by a ``.pth`` line, so every interpreter that venv starts is traced
no matter how an agent invokes it.  It records which public rietx entry points a
run actually reached -- the round's whole read-out -- so the condition is
enforced by the environment rather than asked for in a prompt.

One JSONL line per event, appended with O_APPEND so concurrent runs interleave
safely.  Round 1.1 gives **each run its own venv with its own log path baked
in**, which is what makes attribution a property of the environment instead of
an inference from which file a process happened to touch; ``RIETX_SURFACE_LOG``
stays as a fallback and is not how a 1.1 run is attributed.

Three things a reader of the log has to know, all declared in PROTOCOL.md 1.1:

* **A row is written when the call returns**, carrying ``dt``, its elapsed
  seconds, and ``ok``.  A process killed mid-call therefore leaves no row for
  it, which is the price of timing the call at all.
* **``depth`` is how deep the call sat inside other traced calls**, and it is
  load-bearing rather than decorative: ``rx.refine`` *is* ``Refinement.fit`` one
  frame down, and ``refine_sequential`` *is* ``SequentialRefinement.fit``, so
  summing seconds over names double-counts every fit unless the sum is taken at
  ``depth == 0``.
* **Keyword names always, values only from ``_VALUE_KWARGS``** -- an enum, a
  bool or a preset name, never user data.  Three of the round's read-outs turn
  on *which* value was passed rather than on whether a keyword was.
"""

from __future__ import annotations

import atexit
import functools
import json
import os
import sys
import threading
import time
from importlib.abc import MetaPathFinder
from importlib.machinery import PathFinder

# The interpreter's own start, near enough: a ``.pth`` runs before user code.
_T0 = time.time()

LOG = os.environ.get(
    "RIETX_SURFACE_LOG",
    "/Users/yue/.claude/jobs/9d6b0544/tmp/surface_trace.jsonl",
)

# dotted attribute paths below the ``rietx`` module, resolved after it executes.
# Round 1.0 traced four more, the JSON envelope's calls, and its headline result
# was that no unaided cell reached any of them; WP-1303 then deleted them, so
# they are gone from here too -- a target that cannot be reached is a read-out
# that cannot fail.  ``SequentialRefinement.run`` went the same way for the
# opposite reason: it was renamed to ``.fit``, and a stale target scores a
# rename as a surface nobody reached.  What round 1.0 measured stands in
# PROTOCOL.md; this list is 1.1's, and that document declares it.
_TARGETS = (
    # entry
    "capabilities", "read_pattern", "crystallography.cif.structure_from_cif",
    "read_recipe", "write_recipe_tables",
    # fitting
    "refine", "refine_sequential", "refine_joint", "replay",
    "Refinement.fit", "Refinement.run_stage", "Refinement.predict",
    "SequentialRefinement.fit",
    # judging
    "build_report", "diagnose", "Refinement.report", "Refinement.summary",
    "Refinement.suggest",
    # the parameter table
    "Refinement.parameters", "Refinement.set_vary", "Refinement.set_values",
    "Refinement.tie", "Refinement.tie_equal", "Refinement.untie",
    # help
    "help_for", "help_key_for", "help_registry",
    # pictures
    "viz.plot_result", "viz.plot_for_vlm", "viz.write_html",
    # the rest
    "index_pattern", "auto_background",
    "load_instrument_profile", "save_instrument_profile",
    "Refinement.branch", "Refinement.checkout",
    "Project.create", "Project.open", "Project.save",
)

# Targets that are not reachable from the ``rietx`` module object alone, as
# ``module.attr`` chains from somewhere else.  ``SeriesResult`` is a result
# type rather than an entry point, and R11 turns on whether its summary was
# printed with a declared deliverable.
_EXTRA_TARGETS = (
    ("rietx.sequential", "SeriesResult.summary"),
    ("rietx.examples", "list_examples"),
)

# Values recorded beside the keyword names.  Every one is an enum, a bool or a
# preset name; ``plan`` is recorded only when it is a string, because the other
# form is a whole object.
_VALUE_KWARGS = frozenset({
    "deliverable", "direction", "refit", "mode", "preset",
    "verify_discontinuities", "plan",
})

_state = threading.local()


def _emit(**fields) -> None:
    # `os.getcwd()` raises when the working directory has been deleted under the
    # process — an agent that runs a script from a temp dir it then removes.  A
    # tracer must never break the run it watches, and this call sits inside a
    # `finally`, so it is guarded like the write below rather than left to raise.
    try:
        cwd = os.getcwd()
    except OSError:
        cwd = None
    fields.update(t=round(time.time(), 3), pid=os.getpid(), cwd=cwd)
    try:
        line = (json.dumps(fields, default=str) + "\n").encode()
    except (TypeError, ValueError):
        return
    try:
        fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    except OSError:
        pass


def _values(kwargs: dict) -> dict:
    out = {}
    for key in _VALUE_KWARGS & set(kwargs):
        value = kwargs[key]
        if isinstance(value, (bool, int, float, str)) or value is None:
            out[key] = value
    return out


def _wrap(owner, attr: str, label: str) -> None:
    """Replace ``owner.attr`` with a logging passthrough.

    ``getattr`` resolves the descriptor for us, so a classmethod comes back
    bound and an instance method comes back as the plain function taking
    ``self`` first: calling ``original(*args)`` is correct either way, and the
    replacement is a plain function in both.
    """
    original = getattr(owner, attr, None)
    if original is None or getattr(original, "_rietx_traced", False):
        return

    def traced(*args, **kwargs):
        # the first positional argument is logged ONLY when it is a path -- it
        # is what attributes a process to a workspace when an agent runs python
        # from elsewhere and `python -c` leaves nothing in argv.  No other
        # argument value is recorded except _VALUE_KWARGS.
        path = None
        if args and isinstance(args[0], (str, os.PathLike)):
            candidate = os.fspath(args[0])
            if os.sep in candidate:
                path = candidate
        depth = getattr(_state, "depth", 0)
        _state.depth = depth + 1
        began, ok = time.time(), True
        try:
            return original(*args, **kwargs)
        except BaseException:
            ok = False
            raise
        finally:
            _state.depth = depth
            _emit(event="call", name=label, kwargs=sorted(kwargs),
                  values=_values(kwargs), nargs=len(args), path=path,
                  depth=depth, ok=ok, dt=round(time.time() - began, 4))

    # functools.wraps, not a hand-copied __name__: round 1.0 wrapped without it,
    # so inspect.signature showed `traced(*args, **kwargs)` and one agent went to
    # source to recover a signature.  A shim the subject can see is an
    # observation effect, and this is the cheapest way to close it.
    functools.update_wrapper(traced, original)
    traced._rietx_traced = True
    try:
        setattr(owner, attr, traced)
    except (AttributeError, TypeError):
        pass


def _resolve(root, dotted: str):
    """``root`` walked down ``dotted``'s owner, or None if a step is missing."""
    owner, _, attr = dotted.rpartition(".")
    target = root
    for part in owner.split("."):
        if not part:
            continue
        target = getattr(target, part, None)
        if target is None:
            return None, attr
    return target, attr


def _patch(module) -> None:
    import importlib

    for name in ("rietx.crystallography.cif", "rietx.viz", "rietx.sequential"):
        try:
            importlib.import_module(name)
        except Exception:
            pass

    missing = []
    for dotted in _TARGETS:
        owner, attr = _resolve(module, dotted)
        if owner is None or getattr(owner, attr, None) is None:
            missing.append(dotted)
            continue
        _wrap(owner, attr, dotted)
    for module_name, dotted in _EXTRA_TARGETS:
        try:
            root = importlib.import_module(module_name)
        except Exception:
            missing.append(dotted)
            continue
        owner, attr = _resolve(root, dotted)
        if owner is None or getattr(owner, attr, None) is None:
            missing.append(dotted)
            continue
        _wrap(owner, attr, dotted)

    # A target that does not resolve is reported, never swallowed: an unreached
    # surface and a misspelled one look identical in the log otherwise, which is
    # how round 1.0 would have scored `SequentialRefinement.run`'s rename.
    _emit(event="import", argv=sys.argv[:12],
          import_dt=round(time.time() - _T0, 4), missing=missing,
          version=getattr(module, "__version__", None))


def _exit_wall() -> None:
    _emit(event="exit", wall=round(time.time() - _T0, 4))


class _Patcher(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != "rietx":
            return None
        spec = PathFinder.find_spec(fullname, path)  # bypasses meta_path
        if spec is None or spec.loader is None:
            return None
        loader = spec.loader
        original_exec = loader.exec_module

        def exec_module(module):
            original_exec(module)
            try:
                _patch(module)
            except Exception:  # a tracer must never break the run it watches
                pass

        loader.exec_module = exec_module
        return spec


if not any(isinstance(f, _Patcher) for f in sys.meta_path):
    sys.meta_path.insert(0, _Patcher())
    # R8's denominator: the whole life of any interpreter that imported this,
    # whether or not it went on to import rietx.  Registered here rather than in
    # _patch so a process that starts, imports nothing and exits still counts
    # against the floor it paid.
    atexit.register(_exit_wall)
