"""The acceptance suites' diagnostics as alarm-management counts (WP-2037).

    .venv/bin/python -m tests.suite_alarms            # print the summary
    .venv/bin/python -m tests.suite_alarms --write    # re-pin tests/data/suite_alarms.json

The acceptance suites' protocols are reified as the comparison UI's standards
(``rietx.viz.compare.STANDARDS``, held field by field to the suites by
``tests/test_compare_ui.py``), so :func:`collect` fits each standard's own
protocol once, unmodified, and :func:`firing_table` reduces the fits to the
numbers ``tests/test_suite_alarms.py`` pins: per standard, the codes that fired
and the levels they were raised at, and over all of them each code's count of
standards fired on and the warnings a fit carries per purpose
(``rx.diagnostics_summary``).

**The pin is a prompt, never a verdict.**  The standards are rietx's own data,
so a code firing on every one of them may mean every one of them has the
fault.  A high rate sends that code to the mechanical ground's test, a known
truth where it must fire and one where it must not, and re-levels nothing by
itself (DESIGN.md § Rules 3).  What the pin buys is that a change moving
these numbers is seen.

Every fit writes its obs/calc/diff figure to ``tests/output/`` (gitignored),
as every test refinement does.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import rietx as rx
from rietx._about import DIST_NAME
from rietx.viz import compare

TESTS_DIR = Path(__file__).resolve().parent
PIN = TESTS_DIR / "data" / "suite_alarms.json"
OUTPUT = TESTS_DIR / "output"
REPIN = "python -m tests.suite_alarms --write"


def unavailable(data_dir: Path | None = None) -> dict[str, list[str]]:
    """Each standard whose files are missing under ``data_dir``, with the
    files, so a caller can name what it could not fit."""
    data_dir = Path(data_dir) if data_dir is not None else compare.default_data_dir()
    return {s.key: [f for f in s.files if not (data_dir / f).exists()]
            for s in compare.STANDARDS if not s.available(data_dir)}


def collect(data_dir: Path | None = None, *, plots: bool = True) -> dict[str, rx.RefinementResult]:
    """Fit every available standard under its reference protocol, once.

    The fit is :func:`rietx.viz.compare.run`'s with no variant applied, kept
    whole here because a ``RunRecord`` carries its diagnostics as dicts
    rather than the result.  A standard whose files are missing is left out
    and named by :func:`unavailable`.
    """
    data_dir = Path(data_dir) if data_dir is not None else compare.default_data_dir()
    if plots:
        from rietx.viz.plots import plot_result
        OUTPUT.mkdir(exist_ok=True)
    out = {}
    for standard in compare.STANDARDS:
        if not standard.available(data_dir):
            continue
        inputs = standard.build(data_dir)
        ref = rx.Refinement(inputs.structure, inputs.instrument, history=False)
        result = ref.fit(inputs.data, plan=inputs.plan, telemetry=False,
                         two_theta_limits=inputs.two_theta_limits)
        out[standard.key] = result
        if plots:
            plot_result(result, path=str(OUTPUT / f"suite_alarms_{standard.key}.png"))
    return out


def firing_table(results: dict[str, rx.RefinementResult]) -> dict:
    """The numbers the pin holds: per standard, each code and the levels it
    was raised at (``"info, warning"`` where it was raised at both); over the batch, each code's count of standards fired on
    and the mean warning rows a fit carries per purpose."""
    summary = rx.diagnostics_summary(list(results.values()))
    return {
        "standards": {key: {code: ", ".join(sorted({d.level for d in r.diagnostics
                                                    if d.code == code}))
                            for code in sorted({d.code for d in r.diagnostics})}
                      for key, r in sorted(results.items())},
        "n_results": {t.code: t.n_results for t in sorted(summary.codes, key=lambda t: t.code)},
        "warnings_per_result": summary.warnings_per_result,
    }


def load_pin(path: Path = PIN) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def differences(pinned: dict, measured: dict) -> list[str]:
    """What moved between the pin and a measurement, one line per change,
    naming the code and the standard it moved on."""
    out = []
    old, new = pinned["standards"], measured["standards"]
    for key in sorted(set(old) | set(new)):
        if key not in new:
            out.append(f"{key}: pinned, not measured")
            continue
        if key not in old:
            out.append(f"{key}: measured, not pinned")
            continue
        for code in sorted(set(old[key]) | set(new[key])):
            was, now = old[key].get(code), new[key].get(code)
            if was != now:
                out.append(f"{key}: {code} {was or 'absent'} -> {now or 'absent'}")
    for code in sorted(set(pinned["n_results"]) | set(measured["n_results"])):
        was, now = pinned["n_results"].get(code, 0), measured["n_results"].get(code, 0)
        if was != now:
            out.append(f"all standards: {code} fired on {was} -> {now}")
    for purpose in sorted(set(pinned["warnings_per_result"]) | set(measured["warnings_per_result"])):
        was = pinned["warnings_per_result"].get(purpose)
        now = measured["warnings_per_result"].get(purpose)
        if was != now:
            out.append(f"all standards: warnings per result under {purpose} {was} -> {now}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--write", action="store_true", help=f"re-pin {PIN.name}")
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    missing = unavailable(args.data_dir)
    for key, files in missing.items():
        print(f"{key}: not fitted, missing {', '.join(files)}", file=sys.stderr)
    started = time.perf_counter()
    results = collect(args.data_dir)
    seconds = time.perf_counter() - started
    print(rx.diagnostics_summary(list(results.values())))
    print(f"{len(results)} standard(s) fitted in {seconds:.0f} s")
    if not args.write:
        return 0
    if missing:
        print(f"refusing to write {PIN.name}: a pin without "
              f"{', '.join(missing)} would drop their rows", file=sys.stderr)
        return 1
    table = firing_table(results)
    pin = {"comment": (f"rx.diagnostics_summary over rietx.viz.compare.STANDARDS' reference "
                       f"fits, a prompt and never a verdict (tests/suite_alarms.py). "
                       f"Re-pin with {REPIN}."),
           "written_on": f"{sys.platform}/{platform.machine()}, {DIST_NAME} {rx.__version__}",
           **table}
    PIN.write_text(json.dumps(pin, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {PIN}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
