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
The entry point (#562 S2b, WP number pending) is three more:
:mod:`~rietx.solve.workflow`, ``solve_structure`` — the units (the race over a
composition's site-class assignments, the seeds, the prior-off control seeds,
a consensus per space group) on the event stream and the cancel token ``fit``
uses, checkpointed and resumable (#998), and ``merge_seed_results`` for seeds
run as separate processes; :mod:`~rietx.solve.solution`, the answer: ranked
candidates with their evidence, no structure of its own and no grade; and
:mod:`~rietx.solve.engines`, the run's settings, every search setting the
caller's, and the engine registry.
Nothing here is exported from :mod:`rietx`; the package becomes public, as a
provisional module, when the entry point is exported.
"""
