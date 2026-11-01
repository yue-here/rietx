"""Replay validation schedules offline on probe 16's measured clock and costs.

Each case gives the clock left when validation starts and every checked
candidate's unbudgeted fit cost, in the order today's loop visits them (rank
order).  A schedule decides each fit's slice; a fit whose cost is within its
slice validates and spends its cost, one that is not spends its slice and
reads ``not_validated``.  This is the loop in ``index_pattern`` with the
fits' costs fixed, so it ranks schedules and does not time them.

    python probe18_simulate.py rows16.log
"""
from __future__ import annotations

import json
import sys

#: each dataset's true lattice, as (system, centring, conventional volume)
TRUTH = {
    "nac": ("cubic", "I", 1077.2), "zircon": ("tetragonal", "I", 260.8),
    "fap": ("hexagonal", "P", 523.8), "corundum": ("trigonal", "R", 254.8),
    "lab6": ("cubic", "P", 71.8), "zincite": ("hexagonal", "P", 47.6),
    "magnetite": ("cubic", "F", 591.5),
}


def is_truth(case, fit):
    system, centring, volume = TRUTH[case.split("_")[0]]
    return (fit["system"] == system and fit["centring"] == centring
            and abs(fit["volume"] / volume - 1.0) < 0.01)


def equal(order, R, cost):
    """Today: each fit an equal share of what remains."""
    out = []
    for pos, i in enumerate(order):
        share = R / (len(order) - pos)
        ok = cost[i] <= share
        R -= cost[i] if ok else share
        out.append((i, ok))
    return out


def leader(order, R, cost):
    """(f) as first written: the leader gets the whole clock, the rest share."""
    out = []
    for pos, i in enumerate(order):
        share = R if pos == 0 else R / (len(order) - pos)
        ok = cost[i] <= share
        R -= cost[i] if ok else share
        out.append((i, ok))
    return out


def greedy(order, R, cost):
    """No slices: each fit runs until it ends or the run's clock does."""
    out = []
    for i in order:
        ok = cost[i] <= R
        R -= cost[i] if ok else R
        out.append((i, ok))
    return out


def halving(order, R, cost):
    """Successive halving's simplest form: an equal share for everyone, then
    a second pass over the ones that ran out, in rank order, each refitted
    from scratch on everything left."""
    out = {}
    for pos, i in enumerate(order):
        share = R / (2 * (len(order) - pos))    # half the clock for pass one
        out[i] = cost[i] <= share
        R -= cost[i] if out[i] else share
    for i in [i for i in order if not out[i]]:
        if cost[i] <= R:
            out[i] = True
            R -= cost[i]
    return list(out.items())


POLICIES = {"equal": equal, "leader": leader, "greedy": greedy,
            "halving": halving}


def by_size(fits):
    return sorted(range(len(fits)), key=lambda i: fits[i]["n_refl"])


def main(path):
    for line in open(path, encoding="utf-8"):
        if not line.startswith("{"):
            continue
        rec = json.loads(line)
        fits = rec["fits"]
        if not fits:
            print(rec["case"], "no validation fits")
            continue
        R = 120.0 - rec["first_entry"]
        cost = [f["cost"] for f in fits]
        rank = list(range(len(fits)))
        truth = [i for i, f in enumerate(fits) if is_truth(rec["case"], f)]
        print(f"\n{rec['case']}: {len(fits)} checked, clock left {R:.1f} s, "
              f"truth at visit {truth}, quick validated "
              f"{sum(f['quick_status'] != 'cancelled' for f in fits)}")
        print("  costs (s, n_refl):",
              [(f["cost"], f["n_refl"]) for f in fits])
        for orders, ordering in ((rank, "rank"), (by_size(fits), "size")):
            for name, policy in POLICIES.items():
                got = policy(orders, R, cost)
                ok = [i for i, good in got if good]
                print(f"  {ordering:4s} {name:8s} validated {len(ok):2d}  "
                      f"leader {'Y' if 0 in ok else '-'}  "
                      f"truth {'Y' if any(t in ok for t in truth) else '-'}")


if __name__ == "__main__":
    main(sys.argv[1])
