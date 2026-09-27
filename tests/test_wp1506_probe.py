"""WP-1506 probe: one CI leg fails on purpose.  Throwaway, never merged."""

import sys

if sys.version_info >= (3, 14):
    raise RuntimeError("WP-1506 probe: the py3.14 leg fails on purpose")


def test_the_other_legs_pass():
    pass
