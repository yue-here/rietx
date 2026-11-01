"""The skill body's worked default (`docs/skill/rietx/SKILL.md` § 10), run.

§ 10 is the block an agent copies when it holds a Bragg-Brentano lab pattern
and a CIF and nothing else, so it has to run as written. Below it is verbatim,
except that the one line naming `sample.xy` and `phase.cif` is replaced by two
naming real files. The block shows no number specific to any one pattern:
generic names, the fitted range read from the data, the width seed measured
off its own peaks. So this script is a runnable check of generic code, not a
tuning to this file.

Data: GSAS-II tutorials `LabData`, `FAP.XRA` (Cu Kα, Bragg-Brentano), and
`fluorapatite.cif`, the starting model transcribed from the same tutorial.
Provenance and licence for both: `tests/data/README.md`.

**Two copies, held equal by a test.** The skill body cannot
`{literalinclude}` this file, because an agent reads `SKILL.md` raw, so
`tests/test_skill.py` asserts the two blocks agree line for line. The manual
does not render the body; `docs/docs/reference/agents.md` points at it.
It writes no output file, so it runs from any cwd.
"""

# I001: the two imports below are the body's, grouped as it groups them.
from pathlib import Path  # noqa: I001

import numpy as np
import rietx as rx

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"
PATTERN, CIF = str(DATA / "FAP.XRA"), str(DATA / "fluorapatite.cif")
data = rx.read_pattern(PATTERN)
structure = rx.Structure.from_cif(CIF)
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
limits = (float(np.min(data.two_theta)), float(np.max(data.two_theta)))  # narrow to what you trust
instrument.background = rx.auto_background(data, kind="chebyshev", two_theta_limits=limits).background

strong = sorted(rx.pick_peaks(data, instrument).peaks, key=lambda p: -p.intensity)[:12]
h = float(np.median([p.fwhm for p in strong]))                           # §1 width seed
instrument.profile.w.value, instrument.profile.x.value = (0.6 * h) ** 2, 0.6 * h

ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=limits)  # zero, no displacement

print(result)                                                            # rule 9
for d in result.diagnostics:
    print(d.level, d.code, d.where, "->", d.suggestion)
report = ref.report(plan="mccusker_structural")
if report.abstained_reason:                                              # rule 18
    print("Layer 1 abstained:", report.abstained_kind, report.abstained_reason)
print([u for u in report.unmatched if u.kind == "unmatched_obs"])        # rule 11
print(ref.summary(deliverable="structure", report=report))               # §4b
