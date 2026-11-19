# WP-2224's probe

The scripts behind WP-2224 § Measured. They fit the eight comparison standards
(`rietx.viz.compare.STANDARDS`, data under `tests/data`) under several plans and from several
starts, and count which fits reach the staged plan's answer.

```sh
RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2224-batch/probe.py out.jsonl
.venv/bin/python docs/wp/2224-batch/summarise.py out.jsonl
```

`probe.py`'s docstring lists the plans ("arms") and the starts, and its optional arguments
select a subset. A full run of every arm takes about an hour, most of it in one-stage fits that
fail from a cold start and then run to their evaluation cap. `single+close` on a failed fit ran
for up to 336 s, so leave that arm out unless it is the one being measured.

`summary.txt` is `summarise.py`'s output for the run of 2026-11-19 (macOS arm64, `[dev]`,
telemetry off, tree at 936d17315). Its baseline is the staged plan without a closing stage, from
the standard's own start. A fit "reached" the answer when its Rwp is within 3 % of the
baseline's. The raw JSON lines are not committed (1.2 MB).

`swap.py` is task 3's probe (a block added at its no-effect value, then one stage against
staged), and `accept.py` the § Acceptance run on the eight standards. Each docstring says what
it prints.

Two cautions on the times in `summary.txt`:

- The first pass ran under a load average of 46-71 on ten cores, and it covered the `shipped`,
  `staged`, `single`, `single+2pc`, `single+close`, `two` and `two+2pc` arms of SRM 660c,
  corundum, zincite, fluorite and brucite. SRM 660c's `own` and `warm` rows were timed again on
  a quiet machine. Quote the medians and ranges, and re-time before quoting a single row.
- `corundum own staged` (0.51 s) is a loaded timing. The quiet `staged:1e-4,1e-9` row beside it
  (0.26 s) shows the scale of the error, so the `0.50`-ish lower ends of the `staged:*` ranges
  come from that one row.
