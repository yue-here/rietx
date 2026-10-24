"""WP-2037 — the test of silence: each warning code fires on its fault and on
nothing near it.

``tests/silence.py`` holds the pairs and says how to add one.  A code whose
audit row declares ``response="warning"`` fails here until it has a pair; every
other warning code is listed by ``python -m tests.silence`` and fails nothing.
"""

from __future__ import annotations

import pytest

from rietx.help import DIAGNOSTIC_HELP
from tests import silence
from tests.silence import SILENCE


@pytest.mark.parametrize("code", sorted(SILENCE))
def test_a_warning_fires_on_its_fault_and_stays_silent_beside_it(code):
    pair = SILENCE[code]
    fired = silence.codes(pair.fires())
    assert code in fired, (f"{code} did not fire on its fixture (from {pair.source}); "
                           f"the call raised {sorted(fired) or 'nothing'}")
    quiet = silence.codes(pair.silent())
    assert code not in quiet, (f"{code} fired on its silent fixture (from {pair.source}), "
                               "where nothing it warns about is wrong")


def test_every_code_declared_a_warning_has_a_silence_pair():
    """The enforced half: an audit that gives a code ``response="warning"``
    adds its pair in the same change."""
    without = [code for code in silence.declared_warnings() if code not in SILENCE]
    assert not without, (
        f"{len(without)} code(s) whose row in rietx._audit.ROWS declares "
        f"response='warning' have no silence pair: {without}.  Add a Pair to SILENCE "
        "in tests/silence.py: a fixture where the code must fire and one where it "
        "must stay silent, each calling the narrowest function that raises it "
        "(that module's docstring says how).")


def test_every_pair_is_a_code_the_help_registry_describes():
    unknown = sorted(SILENCE.keys() - DIAGNOSTIC_HELP.keys())
    assert not unknown, f"SILENCE keys naming no code in rietx.help.DIAGNOSTIC_HELP: {unknown}"


def test_the_listed_half_names_only_real_warning_codes_without_a_pair():
    """``missing()`` reads the raise-site walk; what it lists fails nothing."""
    listed = silence.missing()
    assert listed == sorted(set(listed))
    assert not set(listed) & SILENCE.keys()
    assert set(listed) <= DIAGNOSTIC_HELP.keys(), sorted(set(listed) - DIAGNOSTIC_HELP.keys())
    assert set(silence.declared_warnings()) <= set(silence.warning_codes())
