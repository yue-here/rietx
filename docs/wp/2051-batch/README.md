# WP-2051's probes

The scripts behind WP-2051's Context. Like WP-2047's
([`2047-batch/`](../2047-batch/README.md)), they import `tests.` and take the
repository root as their first argument. They also import `2047-batch/probe7.py`.

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2051-batch/resize_profile.py . cpd1a
```

| Script | What it measures | Run time, one run on 2026-10-25 |
|---|---|---|
| `resize_profile.py` | One resize's milliseconds by part (`phase_peaks` memo warm and cold, the k(η) bisection, bounds, FCJ extent and node counts, the batch layout, a whole `rewindow`, a whole `window_sizing` and the layouts a sync rebuilds), median over 40 sizing calls of probe 7's perEval fit | 5-15 s a family |
| `probe9.py` | Probe 7, every mode, with its sizing replaced by `forward.window_sizing` (k(η) off the table). `PROBE9_TAPER=w` tapers the perEval arm's window edge, `PROBE9_TAPER_SIDE=out` outward | as probe 7; `time` 5-25 s a family |
| `probe10.py` | Probe 8 (polished fixed points) on probe 9's arms, the same environment variables | 30-90 s a family |

These scripts are records, not tests. Nothing runs them.
