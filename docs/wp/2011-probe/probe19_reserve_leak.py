"""Where does ``quick``'s validation reserve go on 11-BM NAC?

Probe 16 found NAC's first validation fit starting 121-122 s into a 120 s
run, so the 9.6 s reserve was spent before validation.  This wraps each step
``index_pattern`` takes between the search and the fits (every engine unit,
the merge, the prior build, consensus) and prints when each starts and ends,
relative to the run's start, with the search's own deadline at
120 - 9.6 = 110.4 s.

    python probe19_reserve_leak.py nac_default
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe8_quick import sets  # noqa: E402

import rietx.indexing.engines as eng  # noqa: E402
import rietx.indexing.workflow as wf  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402

T0 = [0.0]
LOG: list[dict] = []


def timed(mod, name, label=None, keyfn=None):
    real = getattr(mod, name)

    def wrapper(*a, **kw):
        t = time.perf_counter() - T0[0]
        try:
            return real(*a, **kw)
        finally:
            rec = dict(step=label or name, start=round(t, 2),
                       end=round(time.perf_counter() - T0[0], 2))
            if keyfn is not None:
                rec["key"] = keyfn(a, kw)
            LOG.append(rec)
    setattr(mod, name, wrapper)
    return real


def main(argv):
    table = sets()
    for name in argv:
        load, spec = table[name]
        data, ins = load()
        peaks = pick_peaks(data, ins)
        wf.VALIDATION_MODE = "pawley"
        real_get = eng.get_engine

        def get_engine(engine_name, _real=real_get):
            fn = _real(engine_name)

            def unit(*a, **kw):
                t = time.perf_counter() - T0[0]
                try:
                    return fn(*a, **kw)
                finally:
                    LOG.append(dict(step=f"unit:{engine_name}:{kw['spec'].systems[0]}",
                                    start=round(t, 2),
                                    end=round(time.perf_counter() - T0[0], 2)))
            return unit
        # index_pattern imports these inside its body, so patch their homes
        eng.get_engine = get_engine
        timed(eng, "merge_engine_units")
        timed(wf, "validate_by_lebail")
        import importlib
        cons = importlib.import_module("rietx.indexing.consensus")
        for fn in ("consensus", "checked_indices", "enumerate_ambiguity"):
            timed(cons, fn)
        T0[0] = time.perf_counter()
        wf.index_pattern(peaks, data=data, instrument=ins, spec=spec)
        LOG.append(dict(step="end", start=round(time.perf_counter() - T0[0], 2)))
        for rec in LOG:
            print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
