- **`solve_magnetic` records every distinct minimum its starts reach** (#1424). `MagneticTrial.minima` lists them lowest χ² first, each with the starts that ended there, its χ² and every site's |m|.
  Minima are now told apart by their moduli, so `MagneticTrial.n_minima` and the "distinct minima" caveat count them that way.
  Before, they were counted by Rwp, which two minima can share: when two sites can swap moduli at about one unit of χ², the old count was wrong on 15 of 24 simulated patterns, reporting one assignment only on 9 of them.
