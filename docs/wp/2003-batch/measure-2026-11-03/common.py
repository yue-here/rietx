import os, platform, sys
os.environ.setdefault("RIETX_TELEMETRY", "0")
SNAP = "/private/tmp/claude-502/-Users-yuewu-Code-rietx/2d6ae8c9-3e42-4d89-bdce-b3f74821ad95/scratchpad/snap"
MEASURE = "/private/tmp/claude-502/-Users-yuewu-Code-rietx/2d6ae8c9-3e42-4d89-bdce-b3f74821ad95/scratchpad/measure"
sys.path.insert(0, SNAP); sys.path.insert(0, SNAP + "/src")
import rietx
assert rietx.__file__.startswith(SNAP), rietx.__file__
from rietx.model import compiled
compiled.set_enabled(True)   # DECLARED: compiled kernel tier requested
import rietx as rx


def env():
    return {"platform": f"{platform.system()} {platform.machine()} ({platform.platform()})",
            "python": platform.python_version(), "rietx": rietx.__version__,
            "rietx_file": rietx.__file__, "venv": "worktree .venv, [dev]",
            "compiled_available": compiled.available(), "compiled_enabled": compiled.enabled(),
            "numeric_path": "compiled tier (set_enabled(True))" if compiled.enabled() else "numpy fallback"}


def cell_a(entry):
    for p in entry.parameters:
        if p.path == "phases.0.cell.a":
            return p.value, p.stderr
    return None, None


def row(e, a_true=None):
    a, s = cell_a(e)
    st = e.statistics
    r = {"index": e.index, "label": e.label, "status": e.status, "rung": e.rung,
         "rungs_tried": list(e.rungs_tried), "n_evals": e.n_iterations,
         "rwp": st.rwp if st else None, "gof": st.gof if st else None,
         "a": a, "a_esd": s, "reseeded": e.reseeded}
    if a_true is not None and a is not None:
        r["a_err_ppm"] = 1e6 * (a - a_true) / a_true
    return r
