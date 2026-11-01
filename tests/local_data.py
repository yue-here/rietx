"""Data a measurement may read on this machine and the repository may not hold (WP-1325).

    python -m tests.local_data                  # fetch every registered dataset
    python -m tests.local_data durham-topas/wo3 # fetch one

**Where it lives.**  One directory outside every checkout, ``$RIETX_LOCAL_DATA``
or else ``~/rietx-local-data``, one subdirectory per source and dataset.  Every
worktree reaches the same copy there.  Removing a worktree or running
``git clean`` cannot take it, and it is never in a commit, a private
repository's included.

**What it holds.**  Public downloads that carry no licence to redistribute
them, kept byte for byte as downloaded.  :data:`DATASETS` registers each file
by URL and sha256.  A second machine then rebuilds the same bytes, and a
measurement can say which bytes it read.  Unpublished data may sit in the same
directory but is never registered here: it is cited by its corpus-map label
(root CLAUDE.md § Licensing), and the map records where it lives.

**What a reader does without it.**  It declines or skips, and never fails.  CI
and cloud sessions have none of this data.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

from rietx._about import DIST_NAME

ROOT_ENV = f"{DIST_NAME.upper()}_LOCAL_DATA"
DEFAULT_ROOT = Path.home() / f"{DIST_NAME}-local-data"

_DURHAM = "https://topas.webspace.durham.ac.uk/wp-content/uploads/sites/261/"

#: dataset -> {file name: (source, sha256)}.  A source is a URL, or the name of
#: a zip registered earlier in the same dataset that holds the file.  Hashes
#: were taken on 2026-10-14.
DATASETS: dict[str, dict[str, tuple[str, str]]] = {
    # Durham TOPAS tutorial 9.2: ZrMo2O8 on a temperature ramp, one Bruker RAW
    # with 82 ranges, of which the tutorial's inputs read the first 68.
    "durham-topas/zrmo2o8_vt": {
        "zrmo2o8_vt.zip": (
            _DURHAM + "2026/04/zrmo2o8_vt.zip",
            "69c406b9ff4be5e3cb49c434b6fd8e78d36c77291930ae8f59aaef11e1ab99b7",
        ),
        "d8_01612.raw": (
            "zrmo2o8_vt.zip",
            "762e403f948c55a38937446875809b3c2b3afec81d21df41d1732057e1bfed8b",
        ),
        "d8_01612_fit_01.inp": (
            "zrmo2o8_vt.zip",
            "cf4c42ebe2217e1b486b8c2386b5833e60d3777eb0b0867a399af187143f152e",
        ),
        "d8_01612_vt_02.inp": (
            "zrmo2o8_vt.zip",
            "f5b6a6109283328b1a66ad93c123efc5b4cfc1e8d183ce1705f73eb1db667318",
        ),
        "d8_01612_vt_reel_01.inp": (
            "zrmo2o8_vt.zip",
            "f2ceb549bc518f6ac26d4948001f339f49ba1c0365c58b3485691dc3759f97fe",
        ),
        "d8_01612_vt_reel_02.inp": (
            "zrmo2o8_vt.zip",
            "6d653b9d53fc7636eea103b181b54b3aa02afa9b6487fbb8b35f1f684de9d647",
        ),
    },
    # Durham TOPAS tutorial "Structure solution - inorganics": the PbSO4
    # round-robin X-ray pattern (Hill 1992, J. Appl. Cryst. 25, 589) as a
    # Bruker RAW version 2 file, the v2 reader's one real file (WP-2059). The
    # page states no licence. Hash checked again on 2026-10-28.
    "durham-topas/pbso4": {
        "Pbso4.raw": (
            _DURHAM + "2021/08/Pbso4.raw",
            "80e990bc360a3628dca6b0efca3ce03278b00136c4183c2088c0d52041a018d7",
        ),
    },
    # Durham TOPAS tutorial 9.5: ZrP2O7, parametric over temperature (Stinton &
    # Evans 2007, J. Appl. Cryst. 40, 87).
    "durham-topas/zrp2o7": {
        "d8_02999.raw": (
            _DURHAM + "2021/08/d8_02999.raw",
            "561b58e8a167d7add786f37d0cc90cd7b39bae6c9b7349c2cc8df7afc7085b5f",
        ),
        "d8_02999_35_annotate_04.inp": (
            _DURHAM + "2021/08/d8_02999_35_annotate_04.inp",
            "042cf10c8aebb552680b559a45eb90a423f2a72bfef571cd14e152a96f47616a",
        ),
    },
    # Durham TOPAS tutorials 9.3 and 9.4: WO3, 100 patterns cooled from 300 to
    # 90 K through its phase transitions, with three starting structures.
    "durham-topas/wo3": {
        "d9_02592.raw": (
            _DURHAM + "2021/08/d9_02592.raw",
            "d8b7c43f81665353f51ea2daf4a2c9754c8895d9717f12deb83b966f3459de00",
        ),
        "wo3_p21n_80056.cif": (
            _DURHAM + "2021/08/wo3_p21n_80056.cif",
            "6e83c4e162776c5f97c136fea85ebc6d4384fab294e1c35f2404b03061f297a2",
        ),
        "wo3_pb1_80053.cif": (
            _DURHAM + "2021/08/wo3_pb1_80053.cif",
            "2d11b29c89e8c374724f00a2395c584c3113256c327fe73d1f8e01d00d47b376",
        ),
        "wo3_pc_84843.cif": (
            _DURHAM + "2021/08/wo3_pc_84843.cif",
            "775ec7a6ee793aa83d050a0dffbe57c5ecd7913c59250d31f2384a3992c3ce43",
        ),
        "d9_02592_3phase_01.inp": (
            _DURHAM + "2021/08/d9_02592_3phase_01.inp",
            "21bd9fbe40dad5217c2074e5fb5f86c21e66654553fc854c65ee9ff3c2642249",
        ),
        "d9_02592_p21n_01.inp": (
            _DURHAM + "2021/08/d9_02592_p21n_01.inp",
            "a8244b8aa60e17971a39ffe6203926d04cb1552a21d29e6a4d38d703b20ab2a5",
        ),
        "d9_02592_pb1_01.inp": (
            _DURHAM + "2021/08/d9_02592_pb1_01.inp",
            "827a1a8e9129097de8135e1f65995368e56590919a717be57010789f7214740a",
        ),
        "wo3_t0000_04.inp": (
            _DURHAM + "2021/08/wo3_t0000_04.inp",
            "e295f25480059a067d2bfecce0246ea9140d7df2a5496550209ba7b1b2071a84",
        ),
        "parametric_04.inp": (
            _DURHAM + "2021/08/parametric_04.inp",
            "bb83bf04265da335254eb0daaebe032481122036c185c88ce775d5e052478552",
        ),
        "parametric_05.inp": (
            _DURHAM + "2023/11/parametric_05.inp",
            "7fadebd03d56324e020d32afd8e963aa2bdbc1b5992caf2ffd2ba3438f3d9962",
        ),
        "parametric_06.zip": (
            _DURHAM + "2026/07/parametric_06.zip",
            "b38e701071b995ad7621bbabd28086d74e5f9df5b2eb04f8dd749c31d0a6fa81",
        ),
    },
}


def root() -> Path:
    """The local data directory, whether or not it exists yet."""
    return Path(os.environ.get(ROOT_ENV) or DEFAULT_ROOT).expanduser()


def _sha256(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def dataset(name: str) -> Path | None:
    """The dataset's directory, or None when any registered file is absent.

    A file that is present with other bytes raises, because a measurement on
    it would not be a measurement on the registered data.
    """
    where = root() / name
    for fname, (_, digest) in DATASETS[name].items():
        path = where / fname
        if not path.is_file():
            return None
        if _sha256(path) != digest:
            raise ValueError(
                f"{path} is not the registered file (sha256 {digest[:12]}…). "
                f"Delete it and run `python -m tests.local_data {name}`."
            )
    return where


def fetch(name: str) -> Path:
    """Download whatever of the dataset is missing, then check every file."""
    where = root() / name
    where.mkdir(parents=True, exist_ok=True)
    for fname, (source, digest) in DATASETS[name].items():
        path = where / fname
        if path.is_file():
            continue
        part = path.with_name(path.name + ".part")
        if source.startswith("https://"):
            # curl, because urllib stopped at 12.8 of Durham's 17.7 MB without
            # raising, and its default user agent is refused there with a 403.
            subprocess.run(
                ["curl", "-sSfL", "--retry", "3", "-m", "300", "-o", str(part), source],
                check=True,
            )
        else:
            with zipfile.ZipFile(where / source) as archive:
                part.write_bytes(archive.read(fname))
        # checked before it takes its name, so a short download never lands
        # where dataset() would refuse it and a zip is verified before it is read
        if _sha256(part) != digest:
            part.unlink()
            raise ValueError(f"{source} did not give the registered {fname} "
                             f"(sha256 {digest[:12]}…)")
        part.replace(path)
    found = dataset(name)
    assert found is not None
    return found


if __name__ == "__main__":
    for name in sys.argv[1:] or DATASETS:
        print(fetch(name))
