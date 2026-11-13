"""Unapplied edits kept across a close or a crash (WP-2209).

The GUI saves itself: settings persist on the verb, and the model lives in
the project's history.  An edit is *pending* until Apply, and until then it
lives only in the browser.  This module keeps a **recovery copy** of those
pending edits in the person's state directory, one file per project, keyed by
the project's resolved path and kept apart from the project.  The maintainer
ruled for this on 2026-11-09 ("the software field's best practice"): VS Code's
hot-exit backups, Blender's ``quit.blend`` and Office AutoRecover all keep the
recovery copy apart from the real file.

Three rules hold the copy to the project's own rule of one authority per fact
(root CLAUDE.md § Project):

* It holds **proposed** edits only, as the client's own open dict.  It never
  holds a value the project stores, so it cannot disagree with
  ``history.jsonl``; the head it was made against rides beside it, so a reader
  can say the project has moved since.
* It is deleted when the edits are applied, reverted or discarded.  The client
  writes ``None`` for each of those, and :func:`discard` removes the file.
* No project file changes.  A copy made with Save a copy starts with no
  recovered edits, and a folder moved outside the app leaves its copy behind
  under the old key.

Retention follows ``runs.py``'s discipline: **by age and size, never by
count**.  A byte ceiling, a week's floor, oldest first, and a folder over the
ceiling with nothing old enough warns and keeps.  Every delete asks three
questions at the call: a recovery file's name, a direct child of the recovery
folder, and a record carrying :data:`RECORD_TAG`.

A write goes to a temporary name in the same folder and is renamed over the
copy, so a crash during the write leaves the previous copy whole.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

#: The folder under the state directory that holds the copies.
RECOVERY_DIR_NAME = "recovery"

#: What every copy carries in ``record``.  A file without it is never read as
#: a copy and never deleted, which is ``runs.RECORD_TAG``'s rule.
RECORD_TAG = "gui_recovery"

#: The copy's own layout.  The ``draft`` dict inside it is the client's and
#: moves without a bump, as ``ProjectDoc.ui`` does.
FORMAT_VERSION = 1

#: The largest draft accepted, in bytes of JSON.  A pending-edit set is a few
#: kilobytes: every free parameter of a four-phase model typed by hand is under
#: 50 kB.  The cap stops a client defect from filling the disk on every keystroke.
MAX_DRAFT_BYTES = 1 << 20

#: Retention, as ``runs.RETENTION_MAX_BYTES`` and
#: ``runs.RETENTION_MIN_AGE_SECONDS`` are for runs.  The ceiling holds
#: thousands of copies, so in practice it deletes nothing; it bounds a defect.
RETENTION_MAX_BYTES = 16 << 20
RETENTION_MIN_AGE_SECONDS = 7 * 24 * 3600.0

_NAME_RE = re.compile(r"^[0-9a-f]{64}\.json$")
_warned = False
_pruned: set[Path] = set()


def root(state_dir: str | Path) -> Path:
    """The recovery folder under ``state_dir``."""
    return Path(state_dir) / RECOVERY_DIR_NAME


def project_key(project_path: str | Path) -> str:
    """The resolved path the copy is keyed by, as the recent list stores it."""
    return str(Path(project_path).expanduser().resolve())


def path_for(state_dir: str | Path, project_path: str | Path) -> Path:
    """The copy's file: the sha256 of the resolved project path, in hex."""
    return _file_for_key(state_dir, project_key(project_path))


def _file_for_key(state_dir: str | Path, key: str) -> Path:
    """The copy's file for a key already resolved."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return root(state_dir) / f"{digest}.json"


def _load(path: Path) -> dict | None:
    """A copy's record, or ``None`` for anything that is not one."""
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("record") != RECORD_TAG:
        return None
    if not isinstance(record.get("draft"), dict):
        return None
    return record


def read(state_dir: str | Path, project_path: str | Path) -> dict | None:
    """The project's copy, or ``None``.

    The stored path must equal the project's, so a copy is never offered to a
    project it was not made in, whatever the file name says.
    """
    return _read_key(state_dir, project_key(project_path))


def _read_key(state_dir: str | Path, key: str) -> dict | None:
    """The copy stored under ``key``, only when its record names that key."""
    record = _load(_file_for_key(state_dir, key))
    if record is None or record.get("project") != key:
        return None
    return record


def write(state_dir: str | Path, project_path: str | Path, draft: dict,
          head: str | None, *, now: float | None = None) -> dict:
    """Keep ``draft`` as the project's copy and return the record written.

    Raises ``ValueError`` on a draft over :data:`MAX_DRAFT_BYTES` and
    ``OSError`` when the folder cannot be written.
    """
    if not isinstance(draft, dict):
        raise ValueError("a draft is a JSON object")
    text = json.dumps(draft)
    if len(text.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise ValueError(f"the draft is over {MAX_DRAFT_BYTES} bytes; "
                         "pending edits are kept up to that size")
    stamp = time.time() if now is None else now
    record = {
        "record": RECORD_TAG,
        "version": FORMAT_VERSION,
        "project": project_key(project_path),
        "head": head,
        "saved_utc": datetime.fromtimestamp(stamp, UTC).isoformat(timespec="seconds"),
        "draft": draft,
    }
    target = path_for(state_dir, project_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    _replace(target, record)
    _prune_once(target.parent)
    return record


def _replace(target: Path, record: dict) -> None:
    """Write ``record`` to a temporary name beside ``target``, then rename it over.

    The temporary name carries the thread as well as the process: the GUI
    server is a ``ThreadingHTTPServer``, and two writes for one project at once
    (a closing page's ``keepalive`` write beside one in flight, or a second tab)
    must not write into one temporary file.
    """
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(json.dumps(record), encoding="utf-8")
        os.replace(temporary, target)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def discard(state_dir: str | Path, project_path: str | Path) -> bool:
    """Delete the project's copy; ``True`` when one was deleted."""
    target = path_for(state_dir, project_path)
    return _guarded_unlink(target, target.parent)


def move(state_dir: str | Path, source: str | Path, target: str | Path) -> bool:
    """Re-key a copy when the app renames or moves its project.

    ``source`` is the old resolved path, taken before the move, and is the
    old key as given.  Resolved again now it can name the new folder: Windows
    resolves a path to the spelling on disk, so after ``sample.rex`` became
    ``Sample.rex`` the old name resolves to the new one, the key of no copy
    (WP-2143).  The project already stands at ``target``.  ``True`` when a
    copy was moved.
    """
    key = str(source)
    record = _read_key(state_dir, key)
    if record is None:
        return False
    record["project"] = project_key(target)
    destination = path_for(state_dir, target)
    _replace(destination, record)
    old = _file_for_key(state_dir, key)
    if old != destination:
        _guarded_unlink(old, old.parent)
    return True


def _guarded_unlink(path: Path, folder: Path) -> bool:
    """Delete one copy, or refuse and say nothing happened.

    The three guards are asked here, at the call: a recovery file's name, a
    direct child of the recovery folder, and a record carrying
    :data:`RECORD_TAG`.  Nothing else in the GUI deletes a file in the state
    directory, so the guards sit where the call is.
    """
    if not _NAME_RE.match(path.name) or path.parent != folder:
        return False
    if folder.name != RECOVERY_DIR_NAME or path.is_symlink() or not path.is_file():
        return False
    if _load(path) is None:
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def prune(folder: str | Path, *, max_bytes: int = RETENTION_MAX_BYTES,
          min_age_seconds: float = RETENTION_MIN_AGE_SECONDS,
          now: float | None = None) -> list[Path]:
    """Bring the recovery folder under ``max_bytes``, oldest copy first.

    Returns the files removed.  The folder's whole size decides *whether* to
    prune; the age floor and the guards decide *what*.  A folder over the
    ceiling with nothing older than the floor warns once and keeps: a person's
    unapplied edits are worth more than the disk.
    """
    global _warned
    folder = Path(folder)
    now = time.time() if now is None else now
    try:
        entries = [Path(e.path) for e in os.scandir(folder)
                   if e.is_file(follow_symlinks=False)]
    except OSError:
        return []
    sizes: dict[Path, int] = {}
    ages: dict[Path, float] = {}
    for path in entries:
        try:
            stat = path.stat()
        except OSError:
            continue
        sizes[path] = stat.st_size
        ages[path] = stat.st_mtime
    total = sum(sizes.values())
    if total <= max_bytes:
        return []
    candidates = sorted((ages[p], p) for p in sizes
                        if _NAME_RE.match(p.name) and now - ages[p] >= min_age_seconds)
    removed: list[Path] = []
    for _, path in candidates:
        if total <= max_bytes:
            break
        if _guarded_unlink(path, folder):
            total -= sizes[path]
            removed.append(path)
    if total > max_bytes and not _warned:
        _warned = True
        warnings.warn(
            f"the recovery folder {folder} holds {total} bytes, over the "
            f"{max_bytes}-byte ceiling, and nothing more in it is a copy older "
            f"than {min_age_seconds / 86400:.0f} days. Keeping them: unapplied "
            f"edits are worth more than the disk.", stacklevel=2)
    return removed


def _prune_once(folder: Path) -> None:
    """Prune a folder once a process, on its first write."""
    if folder in _pruned:
        return
    _pruned.add(folder)
    prune(folder)
