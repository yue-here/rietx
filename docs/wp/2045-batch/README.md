# WP-2045's probes

These are the scripts behind WP-2045's Context bullets, "What the runaway
is", and the cost table after them. Probes 1-5 run the hostile series'
cpd-1a → cpd-1b as `chained_all` does. They wrap `refine.compile_model`, stop at cpd-1b's runaway closing compile,
and then measure one thing from the captured models. They need the IUCr QPA
round-robin data under `tests/data/qarr`. They import `tests.`, so each takes
the repository root as its one argument:

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2045-batch/probe.py .
```

`OPENBLAS_NUM_THREADS=1` matters on Linux, because WP-2003 measured
`leggauss` at 5.4-6.0 s a call under default threading.

| Script | What it measures | Run time, one run on 2026-10-24 |
|---|---|---|
| `probe.py` | Work at each compile, and Rwp at the runaway answer on the frozen model, on fresh declared- and closing-precision compiles, and at the stage's start | ~20 s |
| `probe2.py` | The warm fit as short recompiling stages, every K = 400, 50, 10 and 3 iterations | ~5 min |
| `probe3.py` | The single frozen warm stage under `ftol` 1e-6 and 1e-9, at `max_iter` 100 and 400 | ~1 min |
| `probe4.py` | The Bragg intensity each stage's frozen windows drop at its answer, and the χ² ratio fresh/frozen | ~1 min |
| `probe5.py` | A re-solve from the runaway answer on fresh windows at `ftol` 1e-6 and 1e-9 | ~3 min |
| `probe6.py` | Option 5's cost on the four acceptance protocols and the mg090 joint fit, emulated through the last declared stage's own `ftol` | ~2 min (macOS arm64, 2026-10-25) |

Probes 1-5 ran on a Linux x86-64 cloud container (4 cores, `[dev]`,
Python 3.12) at `7d24e09e7`, and the numbers are in WP-2045's Context.
`probe6.py` ran on macOS arm64 (`[dev]`) at `ab5922dd3`, before option 5
was built. On a tree with option 5 its two arms run the same schedule.

These scripts are records, not tests. Nothing runs them, so a change to
`compile_model`'s signature or to `CompiledPhase.win`/`fcj_n` can break them
silently. Each one repeats its setup rather than sharing a helper, so each
file is exactly what produced its numbers.

`probe4.py` pairs consecutive compiles as one stage's start and answer.
That held in the recorded run: cpd-1a compiled eight times for its eight
declared stages, then once for the closing stage and once for the final
result. A change that adds a compile inside a stage would split its row.
`probe.py`'s abort test was aligned with the other four's (`axial_sl` > 1 at
a 1e-3 compile) after the run. In the recorded run both tests fire at the
same compile, the twelfth.
