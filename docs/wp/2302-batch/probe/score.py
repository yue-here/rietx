"""Hidden misuse cases, run against each implementer's finished package.

Usage: score.py RUN_DIR   (prints one line per case)
Verdicts: PASS (raises naming the problem, or the mistake defined out of existence with the
right result), WARN (a warning only), LATE (raised after work began), LOUD (an exception that
does not name the argument), FAIL (silent).
"""
import importlib
import subprocess
import sys
import warnings
from pathlib import Path

run = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(run))
mr = importlib.import_module("minirefine")
fitmod = importlib.import_module("minirefine.fitting")
task = "exclude" if "exclude" in run.name else "hold"


def call(fn):
    """Return (exception or None, warnings list, return value, solves done during the call)."""
    before = fitmod.SOLVE_CALLS
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            out = fn()
            exc = None
        except Exception as e:  # noqa: BLE001
            out, exc = None, e
    return exc, [str(x.message) for x in w], out, fitmod.SOLVE_CALLS - before


def loud_verdict(exc, warns, solves, names=()):
    if exc is not None:
        msg = str(exc)
        if solves:
            return "LATE", msg
        if names and not any(n in msg for n in names):
            return "LOUD", f"{type(exc).__name__}: {msg}"
        return "PASS", f"{type(exc).__name__}: {msg}"
    if warns:
        return "WARN", warns[0]
    return "FAIL", "silent"


def report(case, verdict, detail):
    print(f"{run.name:14s} {case:34s} {verdict:5s} {str(detail)[:150]}")


M, P = mr.Model.example, mr.Pattern.example

if task == "hold":
    # H0 functional gate
    m = M()
    exc, w, out, _ = call(lambda: (m.hold(["zero_shift"]), mr.fit(m, P()))[1])
    ok = exc is None and all("zero_shift" not in s.free for s in out.stages) and out.values["zero_shift"] == 0.0
    report("H0 hold survives a plan", "PASS" if ok else "FAIL", exc or "")
    # H1 bare string
    m = M()
    exc, w, out, _ = call(lambda: (m.hold("zero_shift"), mr.fit(m, P()))[1])
    ok = exc is None and all("zero_shift" not in s.free for s in out.stages)
    report("H1 hold('zero_shift') bare str", "PASS" if ok else "FAIL", exc or "")
    # H2 literal typo
    exc, w, out, s = call(lambda: M().hold("zero_shfit"))
    report("H2 hold literal typo", *loud_verdict(exc, w, s))
    # H3 glob matching nothing
    exc, w, out, s = call(lambda: M().hold("cel.*"))
    report("H3 hold glob matching nothing", *loud_verdict(exc, w, s))
    # H4 tied path
    m = M()
    exc, w, out, s = call(lambda: m.hold("cell.b"))
    v, d = loud_verdict(exc, w, s)
    if v == "FAIL":
        r = mr.fit(m, P())
        d = f"returned {out!r}; cell.b moved to {r.values['cell.b']:.3f} (from 5.0)"
    report("H4 hold a tied path", v, d)
    # H5 held then set_vary(True) on it
    m = M()
    m.hold("zero_shift")
    exc, w, out, s = call(lambda: m.set_vary("zero_shift", True))
    v, d = loud_verdict(exc, w, s)
    if v == "FAIL":
        d = f"silent; set_vary returned {out!r}"
    report("H5 set_vary(True) on a held path", v, d)
    # H8 unhold literal typo
    m = M()
    m.hold("zero_shift")
    exc, w, out, s = call(lambda: m.unhold("zero_shfit"))
    report("H8 unhold literal typo", *loud_verdict(exc, w, s))
    # H6 info: unhold a path not held
    exc, w, out, s = call(lambda: M().unhold("scale"))
    report("H6 (info) unhold not-held path", *loud_verdict(exc, w, s))
    # H7 info: the old trap
    m = M()
    m.set_vary("zero_shift", False)
    exc, w, out, s = call(lambda: mr.fit(m, P()))
    diag = getattr(out, "diagnostics", None) if out is not None else None
    report("H7 (info) set_vary False then fit", "INFO",
           f"warnings={w[:1]} diagnostics={diag}")
else:
    N = len(P().two_theta)
    inside = sum(1 for t in P().two_theta if 20.0 <= t <= 30.0)

    def n_ok(r, expect):
        return r is not None and abs(r.n_points - expect) <= 1

    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(20.0, 30.0)]))
    report("E0 exclude one region", "PASS" if exc is None and n_ok(out, N - inside) else "FAIL",
           exc or (out.n_points if out else ""))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(20.0, 30.0)], exclude_policy="zero_weight"))
    report("E1 zero_weight policy", "PASS" if exc is None and n_ok(out, N - inside) else "FAIL",
           exc or (out.n_points if out else ""))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(20.0, 30.0)], exclude_policy="zero-weight"))
    report("E2 policy typo", *loud_verdict(exc, w, s, names=("exclude_policy", "policy")))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(30.0, 20.0)]))
    v, d = loud_verdict(exc, w, s, names=("exclude", "lo", "hi", "interval", "30", "invert", "order"))
    if v == "FAIL":
        d = f"silent; n_points={out.n_points} (reordered would be {N - inside}, ignored {N})"
    report("E3 inverted interval", v, d)
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(20.0, 20.0)]))
    report("E4 empty interval", *loud_verdict(exc, w, s, names=("exclude", "empty", "interval", "20")))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(60.0, 70.0)]))
    report("E5 interval outside the data", *loud_verdict(exc, w, s, names=("exclude", "range", "outside", "60")))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=(20.0, 30.0)))
    if exc is None and n_ok(out, N - inside):
        report("E6 bare tuple, not a list", "PASS", "defined out: read as one region")
    else:
        v, d = loud_verdict(exc, w, s, names=("exclude",))
        if v == "FAIL":
            d = f"silent; n_points={out.n_points}"
        report("E6 bare tuple, not a list", v, d)
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(0.0, 90.0)]))
    report("E7 excludes every channel", *loud_verdict(exc, w, s, names=("exclude", "channel", "every", "all", "no ")))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), exclude=[(20.0, 30.0), (25.0, 35.0)]))
    both = sum(1 for t in P().two_theta if 20.0 <= t <= 35.0)
    report("E9 overlapping intervals", "PASS" if exc is None and n_ok(out, N - both) else "FAIL",
           exc or (out.n_points if out else ""))
    exc, w, out, s = call(lambda: mr.fit(M(), P(), mode="rietvled"))
    report("E8 (info) mode typo, existing arg", *loud_verdict(exc, w, s, names=("mode",)))

res = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(run / "tests")],
                     capture_output=True, text=True, cwd=run)
tail = [ln for ln in res.stdout.splitlines() if ln.strip()][-1:] or ["?"]
report("own test suite", "PASS" if res.returncode == 0 else "FAIL", tail[0])
