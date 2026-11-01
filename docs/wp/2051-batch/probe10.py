"""WP-2051 probe 10: probe 8 with probe 9's sizing and taper.

Probe 8's question, which arm's answer is right, asked of probe 9's perEval
arm: the fast sizing, and the taper when ``PROBE9_TAPER`` sets one.

    PROBE9_TAPER=0.1 OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/probe10.py . FAMILY
"""
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent / "2047-batch"))
sys.path.insert(0, str(here))
import probe8  # noqa: E402
import probe9  # noqa: E402, F401  (patches probe 7's sizing and sync)

if __name__ == "__main__":
    probe8.main(sys.argv[2])
