# WP-2047's probes

These are the scripts behind WP-2047's Context, "The staleness test,
measured". Each wraps `refine.compile_model`, runs one family's fit, and then
measures the staleness candidates from the captured compiles. They import
`tests.`, so each takes the repository root as its first argument. The
`hostile` family needs the IUCr QPA round-robin data under `tests/data/qarr`
and restores the tolerance schedule from before WP-2045's option 5, under which
cpd-1b's warm stage still runs away. One family a process, because `hostile`
patches `RefinementPlan.stage_ftols`:

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe1.py . fap
```

| Script | What it measures | Run time, one run on 2026-10-25 |
|---|---|---|
| `probe1.py` | At each stage's answer: `lost`, the χ² ratio fresh/frozen, how many windows a fresh compile widens, and a fresh compile's seconds against the stage's | 1-4 s a family |
| `probe2.py` | `lost` and the χ² ratio at every accepted iteration of the hostile warm stage's first solve | ~1 min |
| `probe3.py` | `lost` at every accepted iteration of every stage, and beside it the pseudo-Voigt estimate taken off the frozen model alone, with its cost | ~1 min a family, `hostile` ~3 min |
| `probe4.py` | Two recompile rules emulated around the solver (`end`, `chunkN`): answer, evaluations, recompiles and seconds against the shipped tree. Takes `FAMILY ARM`; `hostile5` is the hostile pair under the shipped schedule | 1-7 s a run; `end` on the hostile pair 207 s to over 300 s, stopped by its own limit |

| `probe5.py` | `forward.window_loss` against probe 1's fresh-compile `lost` at every stage answer, with the milliseconds of each | 10-60 s a family |
| `probe6.py` | The shipped report in real fits: each stage's `window_loss`, which fits raise `STAGE_WINDOWS_STALE`, and the fit time with the measurement and with it stubbed out, interleaved. Takes `FAMILY [N]`; `hostile` runs into the closing compile at `axial_sl` 558 and takes tens of minutes, so stop it there | 10-30 s a family |

| `probe7.py` | Windows and FCJ node counts resized at every residual and Jacobian evaluation, emulated by wrapping the solver's closures: answer shift in esd, evaluations, LM terminations, residual calls that changed a window, resizing seconds, and fit seconds against shipped (interleaved, median of 5). Takes `fit hostile\|hostile5 ARM`, `time FAMILY [N]` or `step FAMILY`; `step` measures the jump in cost where a window edge crosses a point. `PROBE7_GUARD` sets the size abort. Written by a subagent lane, its headline numbers re-run by the session | 5 s a hostile run; `time` 5-30 s a family; `step` ~10 s |
| `probe8.py` | Which arm's answer is right: each arm's protocol answer polished at 5e-5 windows to a fixed point, the distance between the two polished points, and χ² at each. Imports probe 7 | 30-90 s a family |

Time probe 6 alone: a pytest run beside it put 389 ms on a 51 ms charge.

All six ran on macOS arm64 (`[dev]`, Python 3.12) at `28c88711d`. The
families are `tests.test_window_domain._protocol`'s four (`lab6`, `fap`,
`cpd1a`, `nac`) plus `hostile`.

These scripts are records, not tests. Nothing runs them, so a change to
`compile_model`'s signature, to `CompiledPhase.win` or to the `eval` event's
`values` can break them silently. Probe 3 gives each compile the `eval` events
between it and the next compile, read against the most recent `stage_start`.
A collapse's second solve has its own `stage_start` and no compile, so its
iterations land in the same row as the first solve's: the hostile warm stage
reads 136 iterations, 62 of them the first solve's.
