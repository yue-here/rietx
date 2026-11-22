- **A value held in a series stays held when a pattern is refitted from your own models** (WP-2081).
  When warm starts from the neighbour fail, a series refits the pattern from the models you passed in.
  A parameter held with `ref.hold` in the `constrain` hook used to take your starting value on that refit, and the next pattern carried it on.
  It now keeps the last accepted pattern's value, unless `carry` leaves the path out or a hook set the value for that pattern.
  The `verify_steps` refits hold the value the series held on their own pattern.
  On a LaB₆ ramp with a held zero shift of 0.00797°, the restarted pattern used to hold 0.0 and its cell sat 546 ppm off; it now holds 0.00797° and the cell is within 2 ppm.
  `SeriesEntry.held_values` records every held path's value on each pattern.
