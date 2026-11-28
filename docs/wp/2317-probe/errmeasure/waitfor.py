"""Block until results/ holds N job files matching a prefix, or a timeout (s)."""
import sys
import time
from pathlib import Path

res = Path(__file__).resolve().parent / "results"
n, timeout = int(sys.argv[1]), float(sys.argv[2])
pat = sys.argv[3] if len(sys.argv) > 3 else "*__*__*.json"
t0 = time.time()
while time.time() - t0 < timeout:
    k = len(list(res.glob(pat)))
    if k >= n:
        break
    time.sleep(10)
print(len(list(res.glob(pat))), "files after", round(time.time() - t0), "s")
