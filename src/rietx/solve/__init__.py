"""Structure solution from a verified cell (WP-1515; structure-solution), built in chunks.

Two modules exist so far.  :mod:`~rietx.solve.cost` (WP-1902) is the
whole-profile χ² at a frozen profile, written as a quadratic form in the
per-reflection |F|².  :mod:`~rietx.solve.chemistry` (#562 S3, WP-1997) is what the
chemist knows, as terms reported beside that χ² and never folded into it: the composition gate, the minimum-image contact set, the clash
term, the coordination prior and excluded contacts.  Nothing here is exported
from :mod:`rietx`; the package becomes public, as a provisional module, with
the entry point that returns candidates.
"""
