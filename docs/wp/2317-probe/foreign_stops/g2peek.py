import sys
from GSASII import GSASIIscriptable as G2sc
g = G2sc.G2Project(gpxfile=sys.argv[1])
c = g.data["Covariance"]["data"]
for i,(n,v,s) in enumerate(zip(c["varyList"], c["variables"], c["sig"])): print(i, n, v, s)
