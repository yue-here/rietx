"""Structure solution from a verified cell (WP-1515; structure-solution), built in chunks.

Five modules exist so far.  :mod:`~rietx.solve.cost` (WP-1902) is the
whole-profile χ² at a frozen profile, written as a quadratic form in the
per-reflection |F|².  :mod:`~rietx.solve.chemistry` (#562 S3, WP-1997) is what the
chemist knows, as terms reported beside that χ² and never folded into it: the composition gate, the minimum-image contact set, the clash
term, the coordination prior and excluded contacts.  The direct-space engine
(#562 S2a, WP number pending) is three: :mod:`~rietx.solve.moves`, what a search
moves (free sites on the Wyckoff classes, rigid fragments, the site exchange)
and the |F|² and clash term it sees through the compiled kernels or their numpy
oracles; :mod:`~rietx.solve.tempering`, the planned ladder, one seed of parallel
tempering with its acceptance record, and the polish; and
:mod:`~rietx.solve.cluster`, distinct solutions under the group's Euclidean
normaliser and the ranked list with its evidence, no grade and no structure.
Nothing here is exported from :mod:`rietx`; the package becomes public, as a
provisional module, with the entry point that returns candidates.
"""
