# WP-2006 batch, part 1 (#1058)

What this folder is: the collated material for WP-2006, **no tiers**. Part 2 (the tiers, the six reader decisions
audited by hand, the families for `CIF_ANGLE_CORRECT_MAX_DEG`) waits for the maintainer's gate ruling after WP-2004.
Nothing here rules on or removes anything.

| File | What it is |
|---|---|
| `reachability.csv` | One row per entry of `derive_surface()`: a column per source, `state_use` and `state`. Made by `python -m tests.reachability_walk`. |
| `reachability.md` | Counts, the positive check on the three evidence types, the lists a maintainer would read, the hand checks, what the walk cannot see. |
| `inventory.json` | The codes of `io/` and `crystallography/` (raise site, level, condition, act or judgement), the module-level numbers of both directories with what each decides, the six reader decisions, the GUI's HTTP error names. Made by `collate_inventory.py`. |
| `judgements.json` | The only hand-written input of `collate_inventory.py`: act/judgement per code, role and "decides" per constant, the reader decisions. The script stops on an entry that has none, and on a `decides` or `condition` text that is cut short (it must end in a full stop or a closing bracket, the full stop must not be an abbreviation's, including "p." and "pp.", and no "(" may be left unclosed). |
| `collate_inventory.py` | Derives everything else from the tree (codes via `docs/reference_pages.diagnostic_index()`). |

**Act or judgement** (the `records` field): `act` records something done to or assumed of the file ("was read as", "was
dropped", "was not carried", "was written"); `judgement` asserts something about the data or the file with no change
(`PATTERN_SIGMA_CONSTANT`); `unclear` says in `note` why. An act gated by a threshold or choosing between readings says
so in `note`: the threshold is a judgement under an act, which part 2 tiers separately.
