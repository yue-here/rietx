"""Issue #1376's trial_error unit, at a raised budget, with its peak memory (WP-2110).

    python -m tests.repro_1376 [CEILING] [--cpu-clock] [--trace]

The case is the issue's: glutaric acid–isonicotinamide form II, the published
cell of ``tests/data/cod_1567181.cif`` (P 1 2₁/a 1, a = 26.371, b = 5.2029,
c = 8.904 Å, β = 99.325°), its exact positions at Cu Kα1 over 5–34° 2θ, σ
declared at 0.005°, searched by trial_error alone as monoclinic only, with no
validation.  ``CEILING`` (default 1800 s) is both the whole-run ceiling and the
unit's slice, so a raised ``budget_seconds`` is what this runs.  The reporter's
list had 49 lines; the line count printed here is this build's.

It prints the wall, the process's peak memory (``repro_780.memory_bytes``), the
unit's clock and completeness, and candidate 0.  ``--trace`` adds the sampled
memory curve and the unit's own counters at each base boundary: the solutions
scored (``len(seen)``, since every scored solution entered ``seen`` first),
the candidates held (``len(found)``), the base's assignments (``len(combos)``)
and the CPU clock.  The counters are read by wrapping the module's own
functions, so the engine runs unmodified.  ``--cpu-clock`` is
``repro_780.cpu_clock``: a loaded machine then does the same work.

``--max-gb`` is for a shared machine: once the process's current memory passes
it, the counters so far are printed and the process exits with status 3, so a
profile cannot take its neighbours' memory.  The reporter's peak was 9.2 GB.
"""

from __future__ import annotations

import os

if __name__ == "__main__":
    for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(_var, "1")
    os.environ.setdefault("RIETX_TELEMETRY", "0")

import argparse  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

from tests.repro_780 import MemorySampler, _load, cpu_clock, memory_bytes  # noqa: E402

CIF = Path(__file__).parent / "data" / "cod_1567181.cif"
TWO_THETA_MIN = 5.0
TWO_THETA_MAX = 34.0
ESD_DEG = 0.005


def cell_and_group() -> tuple[tuple[float, ...], str]:
    """The published cell and space group, read from the CIF itself."""
    import gemmi

    block = gemmi.cif.read(str(CIF)).sole_block()
    small = gemmi.make_small_structure_from_block(block)
    uc = small.cell
    cell = (uc.a, uc.b, uc.c, uc.alpha, uc.beta, uc.gamma)
    return cell, small.spacegroup.hm


def peaks():
    """Exact positions at Cu Kα1 over 5–34° 2θ, σ declared (``synthetic_peaks``'s way)."""
    import numpy as np

    from rietx.crystallography.symmetry import generate_reflections
    from rietx.schemas.indexing import PeakList
    from tests.test_indexing_engines import LAM

    cell, group = cell_and_group()
    refl = generate_reflections(group, cell, LAM, TWO_THETA_MAX)
    tt = np.sort(np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d)))))
    tt = tt[tt >= TWO_THETA_MIN]
    return PeakList.from_positions(tt, LAM, two_theta_esd=ESD_DEG)


def spec(ceiling: float):
    from rietx.indexing.engines import SearchSpec

    return SearchSpec(systems=("monoclinic",), budget_seconds=ceiling,
                      total_budget_seconds=ceiling)


class Counters:
    """The unit's counters, read by wrapping ``trial_error``'s own functions.

    One row per base set, taken as the base's ``_combos`` returns: CPU seconds,
    current memory, solutions scored so far, candidates held, the base's
    assignments.  Within the one unit this case runs, scored solutions equal
    ``len(seen)`` because ``_search_system`` adds every key to ``seen``
    immediately before scoring it; the counters are not reset, so a deferred
    dominant-zone probe after an empty harvest would add to them.
    """

    def __init__(self):
        self.rows: list[tuple[float, int | None, int, int, int]] = []
        self.scored = 0
        self.held = 0
        self.dedups: list[tuple[int, int]] = []

    def install(self) -> None:
        from rietx.indexing import trial_error as te

        combos, score, dedup = te._combos, te._score, te.dedup_candidates

        def _combos(per_line):
            out = combos(per_line)
            self.rows.append((time.process_time(), memory_bytes()[0],
                              self.scored, self.held, len(out)))
            return out

        def _score(*args, **kwargs):
            self.scored += 1
            cand = score(*args, **kwargs)
            if cand is not None:
                self.held += 1
            return cand

        def dedup_candidates(cands, *args, **kwargs):
            out = dedup(cands, *args, **kwargs)
            self.dedups.append((len(cands), len(out)))
            self.held = len(out)
            return out

        te._combos, te._score, te.dedup_candidates = _combos, _score, dedup_candidates


def _print_counters(counters: Counters, cpu0: float) -> None:
    gb = 1024.0 ** 3
    print("bases: cpu_s  memory_GB  scored(len seen)  held(len found)  combos")
    for cpu, now, scored, held, n in list(counters.rows):
        mem = f"{now / gb:6.2f}" if now is not None else "   n/a"
        print(f"  {cpu - cpu0:8.1f}  {mem}  {scored:9d}  {held:7d}  {n:8d}")
    print("dedups (in, out):", list(counters.dedups))


def memory_ceiling(max_gb: float, counters: Counters | None) -> None:
    """Exit with status 3, counters printed, once current memory passes ``max_gb``."""
    import threading

    limit, cpu0 = max_gb * 1024.0 ** 3, time.process_time()
    if memory_bytes()[0] is None:
        sys.exit("--max-gb needs a current-memory reading (psutil off macOS)")

    def watch() -> None:
        while True:
            now, _peak = memory_bytes()
            if now is not None and now > limit:
                print(f"memory {now / 1024.0 ** 3:.2f} GB passed --max-gb {max_gb:g}; "
                      f"stopping at cpu {time.process_time() - cpu0:.1f} s", flush=True)
                if counters is not None:
                    _print_counters(counters, cpu0)
                sys.stdout.flush()
                os._exit(3)
            time.sleep(0.25)

    threading.Thread(target=watch, daemon=True).start()


def run(ceiling: float, counters: Counters | None = None) -> dict:
    """One trial_error ``index_pattern`` call on the case."""
    from rietx.indexing.workflow import index_pattern

    pk = peaks()
    if counters is not None:
        counters.install()
    with MemorySampler() as sampler:
        t0, c0 = time.perf_counter(), time.process_time()
        result = index_pattern(pk, spec=spec(ceiling), preset="full",
                               engines=("trial_error",), validate=False)
        wall, cpu = time.perf_counter() - t0, time.process_time() - c0
    return {"result": result, "wall": wall, "cpu": cpu, "cpu0": c0,
            "peak": memory_bytes()[1], "samples": sampler.samples,
            "n_lines": len(pk.q())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ceiling", nargs="?", type=float, default=1800.0)
    parser.add_argument("--cpu-clock", action="store_true",
                        help="count the ceiling in CPU seconds (repro_780.cpu_clock)")
    parser.add_argument("--trace", action="store_true",
                        help="print the memory curve and the per-base counters")
    parser.add_argument("--max-gb", type=float, default=None,
                        help="exit (status 3) once current memory passes this")
    args = parser.parse_args(argv)
    if args.cpu_clock:
        cpu_clock()
    counters = Counters() if args.trace else None
    if args.max_gb is not None:
        memory_ceiling(args.max_gb, counters)

    out = run(args.ceiling, counters)
    res = out["result"]
    gb = 1024.0 ** 3
    print(f"lines {out['n_lines']} (reporter: 49)  ceiling {args.ceiling:g} s"
          f"{' (cpu)' if args.cpu_clock else ''}  wall {out['wall']:.1f} s  "
          f"cpu {out['cpu']:.1f} s  peak memory {out['peak'] / gb:.2f} GB  "
          f"load {_load()}")
    for key, value in sorted(res.engine_stats.items()):
        print(f"  {key}: {value:g}")
    print("search_complete:", res.search_complete)
    if res.candidates:
        c = res.candidates[0]
        print("candidate 0:", tuple(round(v, 4) for v in c.cell), c.system,
              c.centring, "found by", sorted(c.found_by))
    print("codes:", sorted({d.code for d in res.diagnostics}))
    if args.trace:
        for t, now in out["samples"]:
            print(f"  {t:7.1f} s  {now / gb:6.2f} GB")
        _print_counters(counters, out["cpu0"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
