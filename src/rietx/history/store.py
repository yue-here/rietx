"""Append-only JSONL persistence for the refinement history DAG.

One JSON object per line: a header, then nodes in creation order, then
annotations.  History is never rewritten, only appended to — the same property
that makes git's reflog a recovery tool, and what lets ``rietx watch`` tail a
running refinement (docs/milestones/v0.2.md, "History / events").

Concurrency: a node record is several kB, far above the size the OS will append
atomically, so **one writer per file**.  Parallel search should give each
worker its own file and merge by reading them all.  A best-effort ``flock``
guards the append where the platform offers one, but nothing here depends on
it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import IO

import numpy as np

from ..schemas.common import STORED_DOCUMENT
from ..schemas.history import HistoryRecord
from ..schemas.migrate import migrate_document_text

try:  # pragma: no cover - platform dependent
    # by name: JupyterLite's Pyodide kernel puts an empty `fcntl` module in
    # sys.modules, which `import fcntl` accepts and `from fcntl import` does not
    from fcntl import LOCK_EX, LOCK_UN, flock
except ImportError:  # pragma: no cover - Windows, and that mock (WP-1966)
    flock = None  # type: ignore[assignment]


@contextmanager
def _locked(handle: IO[str]) -> Iterator[None]:
    if flock is None:  # pragma: no cover - platform dependent
        yield
        return
    try:
        flock(handle.fileno(), LOCK_EX)
    except OSError:  # pragma: no cover - e.g. network filesystems
        yield
        return
    try:
        yield
    finally:
        try:
            flock(handle.fileno(), LOCK_UN)
        except OSError:  # pragma: no cover
            pass


def append_record(path: str | Path, record: HistoryRecord) -> None:
    """Append one record.  Creates the file (and parents) if absent."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8", newline="\n") as fh, _locked(fh):
        fh.write(record.model_dump_json())
        fh.write("\n")
        fh.flush()


def write_records(path: str | Path, records: list[HistoryRecord]) -> None:
    """Rewrite the whole file (used by ``RefinementTree.save``)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as fh, _locked(fh):
        for record in records:
            fh.write(record.model_dump_json())
            fh.write("\n")
        fh.flush()


def read_records(path: str | Path) -> Iterator[HistoryRecord]:
    """Yield validated records.  Blank lines are skipped; bad lines raise."""
    with Path(path).open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                # a tree written by v1.2 spells the component paths the old way
                # in ``free_paths`` and in the stage globs it recorded; repaired
                # here rather than per-field (schemas/migrate.py's docstring)
                line, _ = migrate_document_text(line)
                # and a field a release made required reads at its old
                # placeholder (``STORED_DOCUMENT_READ_POINTS``)
                yield HistoryRecord.model_validate_json(line, context=STORED_DOCUMENT)
            except ValueError as exc:
                raise ValueError(f"{path}:{lineno}: malformed history record") from exc


def fingerprint(two_theta, intensity) -> str:
    """Stable digest of a pattern, so a tree can verify it is being replayed
    against the data it was recorded from."""
    h = hashlib.sha256()
    h.update(np.asarray(two_theta, dtype=np.float64).tobytes())
    h.update(np.asarray(intensity, dtype=np.float64).tobytes())
    return h.hexdigest()[:32]
