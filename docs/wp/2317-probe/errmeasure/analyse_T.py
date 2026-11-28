"""bigcellT (ties decided on the unnudged start): floor and the window readings."""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import analyse as A  # noqa: E402

runs = A.load()
A.FIXTURES = ["bigcellT"]
A.m1(runs, sys.stdout)
print("n_free per seed:", sorted({runs[("bigcellT", "ref", s)]["n_free"]
                                  for s in ["none"] + [str(k) for k in range(10)]}))
for nb in (False, True):
    A.NO_BKG = nb
    r = A.readings(runs, "bigcellT", "cw1e-2", "cw1e-3", 5)
    print(f"cw1e-2 vs cw1e-3, background {'excluded' if nb else 'included'}: "
          f"naive {r['naive']:.3g} ({r['naive_p']}), floor max {r['floor_max']:.2g}, "
          f"floor_sub {r['floor_sub']:.3g}, floor_glob {r['floor_glob']:.3g}, "
          f"paired {r['paired_max']:.3g}/{r['paired_min']:.3g} ({r['paired_p']}), "
          f"pairs {r['pairs']} split {r['split']}, R basins {r['n_basins_R']}")
