"""Local filesystem implementation of the Drive integration.

Drop-in replacement for ``webhook.integration.drive``.  Operates on a folder
at the project root instead of Google Drive.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def seed_snapshot() -> None:
    """Take the initial snapshot so ``list_changes`` detects only future changes.

    Must be called once at startup, before the file watcher begins firing.
    """
    global _last_snapshot

    folder = _resolve_folder()
    _last_snapshot = _scan_folder(folder)
    logger.info("localdrive: seeded snapshot (%d files)", len(_last_snapshot))

# Module-level snapshot so list_changes can compute a diff between calls.
# {path: {"name": str, "md5": str}}
_last_snapshot: dict[str, dict] = {}

_IO_BLOCK_SIZE = 64 * 1024


def connect() -> None:
    """Return a sentinel — no OAuth or network needed for local mode."""
    logger.info("localdrive: connected (no-op)")
    return None


async def list_changes(
    drive_conn: None, page_token: str | None = None
) -> dict:
    """Scan the local watched folder and return changes since the last call.

    *page_token* is ignored — diffs are always relative to the previous
    ``list_changes`` call tracked in the module-level snapshot.
    """
    from webhook.config import settings

    folder = _resolve_folder()
    snapshot = _scan_folder(folder)

    changes: list[dict] = []

    # --- detect additions and updates ---
    for path, info in snapshot.items():
        old = _last_snapshot.get(path)
        if old is None:
            changes.append(
                _make_change(path, info["name"], info["md5"], removed=False)
            )
        elif old["md5"] != info["md5"]:
            changes.append(
                _make_change(path, info["name"], info["md5"], removed=False)
            )

    # --- detect removals ---
    for path, old in _last_snapshot.items():
        if path not in snapshot:
            changes.append(
                _make_change(path, old["name"], old.get("md5", ""), removed=True)
            )

    _last_snapshot.clear()
    _last_snapshot.update(snapshot)

    new_token = str(int(time.time() * 1000))
    logger.info(
        "localdrive: list_changes returned %d changes token=%s",
        len(changes),
        new_token,
    )
    return {"changes": changes, "newStartPageToken": new_token}


async def list_folder_files(drive_conn: None, folder_id: str) -> list[dict]:
    """List all files in the local watched folder."""
    folder = _resolve_folder()
    result = []
    try:
        for entry in sorted(folder.iterdir()):
            if entry.is_file():
                result.append({"id": str(entry), "name": entry.name})
    except FileNotFoundError:
        pass
    return result


async def find_folder(drive_conn: None, name: str) -> str:
    """Create (if needed) and return the path to a folder at the project root."""
    folder = _PROJECT_ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    logger.info("localdrive: find_folder name=%s path=%s", name, folder)
    return str(folder)


async def get_file_metadata(drive_conn: None, file_id: str) -> dict:
    """Return basic metadata for a local file."""
    path = Path(file_id)
    try:
        stat = path.stat()
    except FileNotFoundError:
        return {"id": file_id, "name": path.name, "error": "not found"}
    return {
        "id": file_id,
        "name": path.name,
        "createdTime": _iso(stat.st_ctime),
        "modifiedTime": _iso(stat.st_mtime),
    }


# --- helpers ------------------------------------------------------------------


def _resolve_folder() -> Path:
    from webhook.config import settings

    folder = Path(settings.WATCH_FOLDER_LOCAL.strip())
    if not folder.is_absolute():
        folder = _PROJECT_ROOT / folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _scan_folder(folder: Path) -> dict[str, dict]:
    """Return ``{path: {"name": name, "md5": hexdigest}}`` for every file."""
    snapshot: dict[str, dict] = {}
    try:
        for entry in folder.iterdir():
            if not entry.is_file():
                continue
            md5 = _md5_hex(entry)
            snapshot[str(entry)] = {"name": entry.name, "md5": md5}
    except FileNotFoundError:
        pass
    return snapshot


def _md5_hex(path: Path) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(_IO_BLOCK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


def _make_change(path: str, name: str, md5: str, *, removed: bool) -> dict:
    return {
        "fileId": path,
        "removed": removed,
        "file": {
            "id": path,
            "name": name,
            "md5Checksum": md5,
        },
    }


def _iso(timestamp: float) -> str:
    """Convert a Unix timestamp to ISO-8601 UTC."""
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
