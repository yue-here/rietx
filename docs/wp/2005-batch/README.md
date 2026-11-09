# WP-2005 batch, part 1

What this folder is: the collated inventory for WP-2005, **no tiers**. It follows WP-2006's part 1
(`../2006-batch/`, merged as #1101). The tiers, the lifts and the batch to the maintainer wait for
the maintainer's gate after WP-2004 (`docs/milestones/generality.md` § The order: the maintainer
decides whether 2005 to 2007 run on the counts 2002 to 2004 report). Nothing here rules on,
moves or removes anything.

| File | What it is |
|---|---|
| `inventory.json` | One row per code: raise sites with level and guarding conditions, the named constants its raising function reads (with each one's audit tier and value), the explanation's first sentence, the code's audit rows, the tests naming it, and the hand-written condition and kind of ambiguity. Then one row per numeric literal in a raising function or a same-file function it calls by name, with its role. Made by `collate_inventory.py`. |
| `judgements.json` | The only hand-written input: per code the condition in words and the kind of ambiguity of its verdict (DESIGN.md § Rules, 1) with the reason; per literal its role and the reason. The script stops on a code or literal with none, on a judgement the tree no longer has, and on a text cut short (WP-2006's rule). |
| `collate_inventory.py` | Derives the rest from the tree: codes from `docs/reference_pages.diagnostic_index()`, raise sites and literals by AST, tiers from `rietx._audit.ROWS`, explanations from `rietx.help.DIAGNOSTIC_HELP`. |

Run it with `.venv/bin/python docs/wp/2005-batch/collate_inventory.py`; `--skeleton` prints
what a new judgement needs to read.

## The counts, at `5ae35232c` (2026-11-09)

- **74 codes**, not the WP's 61: 69 raised in `refine.py` (12 241 lines, against 9 587 at the
  WP's opening) and the five the WP names from `background/select.py`, `optimize/qpa.py` and
  `schemas/migrate.py`. 78 raise sites. 64 codes are `unaudited`; 8 are tiered 1 and 2 tiered 3
  already.
- **Kind of ambiguity**, the inventory's reading for part 2 to check: 58 codes state something
  the data settle (an act recorded, a fact of the arithmetic or a published range), 4 name one of
  several explanations the data could rank, and 12 make a verdict the data cannot settle
  (`ABSORPTION_PLATE_THICKNESS`, `BACKGROUND_ABSORPTION`, `BISO_UNUSUALLY_LARGE`,
  `HARMONIC_FRACTION`, `HIGH_CORRELATION`, `LOW_ANGLE_UNMODELLED`, `OCCUPANCY_ABOVE_ONE`,
  `RESTRAINT_TENSION`, `ROUGHNESS_ABSORPTION`, `SIZE_UNUSUALLY_SMALL`, `STAGE_WINDOWS_STALE`,
  `STRAIN_UNUSUALLY_LARGE`). Four of the 74 copy the ambiguity their audit row already carries.
- **34 numeric literals**, not about 30 that gate: 12 convert units, 8 are arithmetic, 3 count,
  3 cap a listing, 3 are numerical floors, and **5 are thresholds**. Four of the five gate
  something in `refine.py`: `0.7` under `ABSORPTION_PLATE_THICKNESS` and `>= 2.0` under
  `LOW_ANGLE_UNMODELLED`'s suggestion, the two the WP names, plus the two-FWHM edge of the
  low-angle region and the half of sin θ_min that sets `ROUGHNESS_OUTSIDE_REGIME`'s info band.
  The fifth refuses a Chebyshev scan in `background/select.py` and gates no code. The other 29 are
  tier 1 by their role, each with its reason in `judgements.json`.
- **35 named constants** are read by a raising function: 21 `unaudited`, 6 tier 3, 4 tier 2,
  3 tier 1 and 1 `invariant`.

## What the walk cannot see

- A threshold that lives in another directory and reaches the code through a finding or a
  statistic: the guard codes' thresholds are in `strategy/staged.py` and `schemas/plan.py`, and
  `PATTERN_DEAD_CHANNELS`'s in `background/diagnostics.py`. The code's `note` names each one it
  could find; those constants are in WP-2002's walk, and B13 handed several here.
- A literal deeper than one call from the raising function, or in a function called through a
  variable. A sweep of every numeric literal in `refine.py` outside the raising functions found 18
  (2 and 100 left out). The helper walk takes in the two a raising function calls; none of the
  other 16 gates a code (parsing, listing caps in errors, the magnetic hold's probes).
- A test that names a code only through a helper in another file. The count reads the test
  function and its decorators, and a module-level name bound to the code (`CODE = "…"`).
