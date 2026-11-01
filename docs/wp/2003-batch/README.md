# WP-2003 batch: the chain actions

The collated material for WP-2003's audit: the inventory, the reseed measurement, and the proposed tiers.
Nothing here rules on, moves or removes anything; the 17 rows that needed no approval are in
`src/rietx/_audit.py` (2026-10-24). The rule it is collated for is `../../milestones/generality.md` § The rule.

| File | What it is |
|---|---|
| `inventory.json` | One object per action and constant (task 1). It holds the 77 `_audit.ROWS` names 2003 owns, `"row": true`: 17 codes and their 17 suggestion rows, 5 `SeriesEntry` actions, 12 constants, 26 defaults at the two sequential seats. It also holds 34 row-less entries, `"row": false`, under proposed names: 18 in `sequential.py`, 16 in the joint fit across `multi.py`, `params/multi.py` and two `optimize/least_squares.py` freezes. |
| `rows.json` | One proposal per inventory entry (task 2): tier, kind of ambiguity, evidence as it would enter the table, grounds, class, demotion, dissenter, response, and the decision owed; `"applied": true` on the 17 written into the table, `"status": "tiered 2026-10-24"` on the 11 before them. Built by hand from the inventory, `reseed.md` and `docs/practice.md`. |
| `classes.md` | The 111 entries in eleven classes, each with its stakes line, decision, evidence, case against and pick: the batch's draft (2026-10-24), its picks superseded by `batch.md`. |
| `batch.md` | The decision batch put to the maintainer: eleven class briefs with their current picks, revised on 2026-10-25 against DESIGN.md § Rules on the numbers re-measured on `main`, the fixes that need no ruling and two investigations owed. |
| `clashes.md` | The clash table, X1-X17: each pair of chain actions that read or move the same thing, measured where possible; X1-X5 and X13 carry dated notes from the 2026-10-25 re-measurement, X16 and X17 are from it. |
| `reseed.md`, `reseed/`, `measure_reseed.py` | The reseed measurement: the script, its JSONs (rewritten 2026-10-25 on `main` at `9ad4d1f6`, every arm) and the 2026-10-24 rendered tables (`reseed.md`; re-render with `--table`). |
| `README.md` | This page, and task 3's question answered below. |

`rows.json` follows `batch.md`: the proposals of C1, C2, C3, C9 and C10 that its 2026-10-25
revision changed carry "(revised 2026-10-25, batch.md)" in `decision`. The entry count is
unchanged; the joint absent-phase hold and its release (`_hold_unsupported_phases_multi`,
`_rehold_multi`) went from `covered` to a proposed row of their own.

The keys: `decides` and `without` say what an entry decides for the caller and what the caller gets without it.
`record` is the result field that reports it acting, `null` where only a message or nothing does. `opt_in` with
`caller_condition_2` tests both caller-class conditions, `false` where a package number inside the switch moves the
answer (named in `note`). `invariant` is the claim and where it is stated or measured; `families` gives test
`file:line`. The 2003 rows include `SERIES_PATTERN_FAILED`, raised in `sequential.py` and missing from the brief's
list. `MultiHistogramRefinement.fit`, `refine_multi` and `SharingMap` are not `DEFAULT_SEATS`: their defaults have no rows.

## Quarantine's record

Does the returned `SeriesResult` name the pattern that diverged, the rung it reached, and the successors seeded from
an earlier pattern instead?

- **(a) The pattern: yes.** `SeriesEntry.status == "diverged"` on its own entry, with `index` and `label`
  (`src/rietx/schemas/sequential.py:55`, copied from the kept attempt at `src/rietx/sequential.py:925-936`).
  `SEQUENTIAL_UNRECOVERED` names it (`sequential.py:2127-2148`), derived from that status, so a reloaded result says the same.
- **(b) The rung: yes.** `SeriesEntry.rung` is the kept rung and `rungs_tried` every rung climbed, with `rungs_raised`
  beside them (`schemas/sequential.py:147-174`, written at `sequential.py:1667-1669`). Under `reseed=False`,
  `rungs_tried` is `["warm"]` *unless* WP-1127's budget truncated the first rung: that escalation is
  forced past `reseed` (`sequential.py:1561`, `1569-1571`), seen at planted pattern 87 in every arm
  (`reseed.md`; corrected 2026-10-24 by the measurement).
- **(c) The successors: no field.** No `SeriesEntry` field says where its warm start came from, and nothing names the
  successor that started from the last accepted pattern in place of the quarantined one (`sequential.py:1697-1710`).
  A reader can only infer it from walk order and each predecessor's `status`. The message says "It seeded no
  successor" and names none (`sequential.py:2143-2146`). `_link_history` writes `series_warm_start_tree`/`_node` on
  each tree root (`sequential.py:1937-1955`), but only with history on, and on the trees, not the result. The default
  is `history=False` (`sequential.py:3065`), under which entries carry no `node_id`/`tree_id`. A `SeriesFailure`
  under `on_error="carry"` has the same gap (`sequential.py:1648-1652`). Per task 3, the field is added whatever the ruling.

**The moment-floor reseed has no record field.** `_floor_unsupported_moments` (`sequential.py:857-922`, applied at
1704-1706) records which successors got a floored warm start only in `_chain`'s local `floored` dict (1493-1500,
returned at 1745). Only `_moment_diagnostics` reads it (1361), and its `SEQUENTIAL_MOMENT_HOLD` message (raise 2675)
names at most four successors (2666-2673). Neither `SeriesEntry` nor `SeriesResult` carries it.
