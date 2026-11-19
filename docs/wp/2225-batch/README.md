# WP-2225's probe

The scripts behind WP-2225 § Measured. They fit the comparison standards
(`rietx.viz.compare.STANDARDS`, data under `tests/data`) and switch the width-twin hold
(`refine._hold_width_twins`) off or change it by monkeypatching the module in the script. Nothing
under `src/` changes.

`import rietx.refine` returns the `refine` function, because the package re-exports it under the
module's name. The scripts reach the module through `sys.modules["rietx.refine"]`. A patch
written against `rietx.refine` patches nothing and reports today's behaviour.

| Script | What it runs |
|---|---|
| `arms.py STD ARM,ARM` | a first staged fit (closing stage off), then each arm from its end point; `NOHOLD=1` switches the hold off. Arms: `staged`, `single`, `single:seed0`, `single:ftol<F>`, `staged:seed0`, `staged:upto<N>`, `staged:ftol<I>;<F>`, `passes<N>`, and `first:<arm>` for the first fit. A trailing `!` prints the λ trace. `spy.py` reports each solve's box bounds and inequality rows at its end; `SPY_JAC=<n>` compares the analytic Jacobian with central differences on the solve with n free columns |
| `eight.py OUT.jsonl` | every standard: first fit, chained staged re-fits until Rwp moves under 1e-7 (at most 6), the same with the hold off, and the shipped default (closing stage on) with one re-fit |
| `shifts.py OUT.jsonl` | reduces `eight.py`'s rows to the largest shift per kind of parameter, in esds of the earlier fit; `eight_summary.txt` is its output |
| `swap.py OUT.jsonl STD,STD` | the prototype: a pair whose specimen twins all sit on their floor at a stage's start holds the twins and frees the instrument column; `swap_summary.txt` is its output |
| `plot_zincite.py` | zincite's shipped first fit against a shipped re-fit, to `tests/output/` |

```sh
RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2225-batch/eight.py out.jsonl
.venv/bin/python docs/wp/2225-batch/shifts.py out.jsonl
```

Measured 2026-11-19, macOS arm64, worktree venv `[dev]`, compiled tier on, telemetry off, tree
`e6b6e9b5c`. Every fit takes 0.3-4 s, and `eight.py` runs in about three minutes. The raw JSON
lines are not committed.
