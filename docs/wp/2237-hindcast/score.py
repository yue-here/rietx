"""Score each arm's predictions against the hidden key."""
import json
import math
import pathlib

H = pathlib.Path(__file__).parent
key = {int(k): v for k, v in json.loads((H / "key.json").read_text(encoding="utf-8")).items()}
DIRECTION = {3, 10, 11}  # also: 5 (reader default) - routing counted separately
for arm in "APRF":
    f = H / f"arm_{arm}.json"
    if not f.exists():
        continue
    rows = {r["case"]: r for r in json.loads(f.read_text(encoding="utf-8"))}
    out = {}
    for subset, ids in (("all14", sorted(key)), ("clean9", [c for c in sorted(key) if not key[c]["leaked"]])):
        ps = [rows[c]["p"].get(key[c]["pick"], 0.0) for c in ids]
        hits = sum(max(rows[c]["p"], key=rows[c]["p"].get) == key[c]["pick"] for c in ids)
        logs = sum(math.log(max(p, 0.01)) for p in ps) / len(ps)
        out[subset] = f"{hits}/{len(ids)} top-pick, mean p(Yue) {sum(ps)/len(ps):.2f}, mean log p {logs:.2f}"
    misses = [c for c in sorted(key) if max(rows[c]["p"], key=rows[c]["p"].get) != key[c]["pick"]]
    bring = [c for c in sorted(key) if rows[c]["route"] == "bring"]
    print(f"arm {arm}: {out['all14']} | clean: {out['clean9']} | missed {misses} | brings {bring}")
