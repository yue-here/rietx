"""Helpers shared by WP-2018's clash measurements (task 3).

Every script runs from the repo root (``python docs/wp/2018-measure/<name>.py``)
and prints one JSON object per arm.  A record names what the caller of a fit
reads: Rwp, the shared parameters with their esds, every diagnostic code with
its paths, and what each stage held, released, collapsed or reset.  PNGs go to
``tests/output/wp2018/`` (gitignored), or ``$WP2018_OUT`` when set.
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path(os.environ.get("WP2018_OUT", ROOT / "tests" / "output" / "wp2018"))


def row(result, path):
    """(value, esd, at_bound) of ``path`` in ``result``, or Nones."""
    for p in result.parameters:
        if p.path == path:
            return p.value, p.stderr, p.at_bound
    return None, None, None


def stages(result):
    """What each stage held, released, collapsed and reset, by path."""
    out = []
    for s in result.stages:
        out.append({
            "stage": s.name, "rwp": s.rwp, "status": s.status,
            "held": list(s.held), "released": list(s.released),
            "collapsed": list(s.collapsed or []),
            "cell_reset": list(s.cell_reset or []),
        })
    return out


def diagnostics(result):
    return [{"code": d.code, "level": d.level, "where": list(d.where),
             "value": d.value, "message": d.message[:240]}
            for d in result.diagnostics]


def record(result, paths):
    return {
        "rwp": result.statistics.rwp, "status": result.status,
        "params": {p: row(result, p) for p in paths},
        "stages": stages(result), "diagnostics": diagnostics(result),
    }


@contextmanager
def patched(module, name, value):
    """Set ``module.name`` for the block and put it back after."""
    old = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, old)


def emit(obj):
    print(json.dumps(obj, default=str), flush=True)


def provenance():
    import platform
    import subprocess

    import rietx
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short=9", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    # relative to the tree: an absolute path names the machine it ran on
    here = Path(rietx.__file__).resolve()
    tree = str(here.relative_to(ROOT)) if here.is_relative_to(ROOT) else "outside this tree"
    return {"commit": sha, "rietx": tree, "machine": platform.machine(),
            "python": platform.python_version(),
            "utc": time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())}
