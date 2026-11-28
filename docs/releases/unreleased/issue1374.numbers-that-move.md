- **Under a whole-run ceiling, each indexing engine gets a share of it on each crystal system** (#1374). With `total_budget_seconds` declared, one engine's search of one system now runs for at most `budget_seconds` or the search's time divided by the number of engines, whichever is shorter.
  Before, a caller who raised `budget_seconds` to the ceiling let the first unfinished search hold all of it, so the other engines never started and the run could return no cell.
  On #1374's 15 synthetic rows the share was never worse; it found the cell in 3 of the 5 rows that returned nothing and added a second finder in 9 of the other 10.
  The default 30 s slice is below the share of the `quick` ceiling (34 s), so a default run is unchanged, and so is a run with no ceiling.
  To give one engine the whole search, name it in `engines`. `INDEX_BUDGET_EXHAUSTED` states the share when it bound.
