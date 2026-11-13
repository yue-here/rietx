"""The fit behind `docs/docs/guides/watch.md`: a fit stopped from its own event stream.

The page shows the lines between the two `guide:` markers and quotes what they
print; every quoted value is asserted below the second marker, so a change that
moves one fails `tests/test_examples.py`.

A real stop comes from another thread or from `rietx watch`.  This one sets the
token from the event callback when the first stage ends, so the run stops at
the same place every time.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
ref = rx.Refinement(structure, instrument)

token = rx.CancelToken()
stopped = None


def on_event(event):
    if event["kind"] == "stage_start":
        print("started", event["data"]["stage"])
    elif event["kind"] == "stage_end":
        print("ended", event["data"]["stage"], event["data"]["status"])
        token.cancel()


try:
    ref.fit(data, plan="mccusker_default", two_theta_limits=(15, 130),
            events=on_event, cancel=token)
except rx.RefinementCancelled as cancelled:
    stopped = cancelled
    print("abandoned:", stopped.stage)
    print("completed:", [stage.name for stage in stopped.completed_stages])
    print("working state at node", stopped.node_id)
# guide: end

assert stopped is not None, "the fit finished: the token never stopped it"
assert stopped.stage == "zero_disp"
assert [stage.name for stage in stopped.completed_stages] == ["scale_bkg"]
assert stopped.node_id is not None
