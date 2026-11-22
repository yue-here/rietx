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
| `arms.py STD ARM,ARM` | a first staged fit (closing stage off), then each arm from its end point; `NOHOLD=1` switches the hold off. Arms: `staged`, `single`, `single:seed0`, `single:ftol<F>`, `staged:seed0`, `staged:upto<N>`, `staged:ftol<I>;<F>`, `passes<N>`, and `first:<arm>` for the first fit. A trailing `!` prints the λ trace. Rows append to `arms_<STD>.jsonl` in the working directory (`ARMS_OUT` overrides). `spy.py` reports each solve's box bounds and inequality rows at its end; `SPY_JAC=<n>` compares the analytic Jacobian with central differences on the solve with n free columns |
| `eight.py OUT.jsonl` | every standard: first fit, chained staged re-fits until Rwp moves under 1e-7 (at most 6), the same with the hold off, and the shipped default (closing stage on) with one re-fit |
| `shifts.py OUT.jsonl` | reduces `eight.py`'s rows to the largest shift per kind of parameter, in esds of the earlier fit; `eight_summary.txt` is its output |
| `swap.py OUT.jsonl STD,STD` | the prototype: a pair whose specimen twins all sit on their floor at a stage's start holds the twins and frees the instrument column; `swap_summary.txt` is its output |
| `eight_summary_axial_first.txt` | `shifts.py` on `eight.py` re-run 2026-11-19 after `qpa_plan` moved `lines_axial` ahead of `sample_broadening` (WP-2225 § Inherited); merged main, closing stage off by default |
| `plot_zincite.py` | zincite's shipped first fit against a shipped re-fit, to `tests/output/` |
| `families.py OUT.jsonl FAMILY,… CLOSING,…` | task 1: today's hold, option 1 (`swap.swap_hold`), option 2 (rounds of the instrument-only stage and the last stage) and the hold off, on cpd-1a from both Biso starts, LaB₆ + cBN, brucite with a Stephens block and the four standards; each first fit then one staged re-fit under the same rule. Figures to `tests/output/wp2225_*.png` |
| `families_summary.py OUT.jsonl …` | reduces `families.py`'s rows; shifts in plain esd, reported esd, and reported esd over cell, atom and scale rows. `families_summary_multi.txt` (cpd-1a, LaB₆ + cBN) and `families_summary_std.txt` (the four standards, brucite with a Stephens block) are its output |

```sh
RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2225-batch/eight.py out.jsonl
.venv/bin/python docs/wp/2225-batch/shifts.py out.jsonl
```

**A second `fit` runs one stage since WP-2224** (`refit="single"`). `eight.py` called `fit` again
with no `refit=` until 2026-11-20, so `eight_summary_axial_first.txt` holds one-stage re-fits in its
`chain` and `shipped+1` rows. Every script here now passes `refit="stages"` for a re-fit, and sets
the closing stage on for a "shipped" row, which the standards' plans have left off since WP-2222.

Measured 2026-11-19, macOS arm64, worktree venv `[dev]`, compiled tier on, telemetry off, tree
`e6b6e9b5c`; `families.py` 2026-11-20, same machine and venv, tree `6c3a2db5e`. Every fit takes 0.3-4 s, and `eight.py` runs in about three minutes. The raw JSON
lines are not committed.
