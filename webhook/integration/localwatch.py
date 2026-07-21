"""Local filesystem-watcher implementation of the Watch integration.

Drop-in replacement for ``webhook.integration.watch``.  Uses ``watchdog``
to observe a local folder and fires HTTP POSTs to the app's own
``/drive/updated`` endpoint whenever a file changes.  The channel never
expires.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime

import httpx
from pydantic import BaseModel
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from webhook import db

logger = logging.getLogger(__name__)

WATCH_TTL_SECONDS = 604800  # kept for API compatibility; never expires locally

_observer: Observer | None = None
_observer_lock = threading.Lock()

# Debounce state
_debounce_timer: threading.Timer | None = None
_debounce_lock = threading.Lock()
_DEBOUNCE_SECONDS = 1.0


class WatchChannelData(BaseModel):
    channel_id: str
    resource_id: str = ""
    resource_uri: str = ""
    expiration: int = 0  # unix millis
    page_token: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


async def get_watcher_channel_data() -> WatchChannelData | None | bool:
    """Return stored channel data from Firestore, or None/False if absent."""
    doc = (await db.get_doc("watch", "drive_channel")).get()
    if not doc.exists:
        return False
    return WatchChannelData(**doc.to_dict())


def channel_expired(channel_data: WatchChannelData) -> bool:
    """Local channels never expire."""
    return False


async def create_watch_channel(
    drive_conn: None, webhook_url: str, watch_folder_id: str
) -> bool:
    """Start a watchdog observer on the local folder.

    On any file event the observer debounces then POSTs to *webhook_url*
    so the app processes the change through the normal request path.
    """
    from webhook.integration.localdrive import _resolve_folder

    global _observer

    folder = _resolve_folder()
    channel_id = str(uuid.uuid4())

    logger.info(
        "localwatch: starting observer channel=%s folder=%s", channel_id, folder
    )

    # Stop any previous observer
    await stop_watch_channel(drive_conn, "")

    handler = _DebouncedHandler(webhook_url, channel_id)
    obs = Observer()
    obs.schedule(handler, str(folder), recursive=False)

    with _observer_lock:
        _observer = obs
        obs.start()

    # Trigger an initial scan so files added while the server was offline
    # are processed.  Schedules a debounced POST — mirroring how Google
    # Drive delivers an async "sync" notification after channel creation.
    handler._schedule()

    # Persist channel info in Firestore
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    now_ms = int(time.time() * 1000)
    await db.update_doc(
        "watch",
        "drive_channel",
        {
            "channel_id": channel_id,
            "resource_id": "",
            "resource_uri": str(folder),
            "expiration": now_ms + WATCH_TTL_SECONDS * 1000,
            "updated_at": now_iso,
        },
    )

    logger.info("localwatch: observer started channel=%s", channel_id)
    return True


async def stop_watch_channel(drive_conn: None, channel_id: str | None = None) -> bool:
    """Stop the running observer, if any."""
    global _observer

    with _observer_lock:
        obs = _observer
        _observer = None

    if obs is None:
        return False

    obs.stop()
    obs.join(timeout=5)
    logger.info("localwatch: observer stopped")
    return True


# --- Debounced watchdog handler ------------------------------------------------


class _DebouncedHandler(FileSystemEventHandler):
    """Coalesce rapid file events into a single HTTP POST."""

    def __init__(self, webhook_url: str, channel_id: str) -> None:
        self._webhook_url = webhook_url
        self._channel_id = channel_id

    # -- watchdog callbacks -------------------------------------------------

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._schedule()

    def on_deleted(self, event) -> None:
        if not event.is_directory:
            self._schedule()

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._schedule()

    def on_moved(self, event) -> None:
        if not event.is_directory:
            self._schedule()

    # -- debounce -----------------------------------------------------------

    def _schedule(self) -> None:
        global _debounce_timer
        with _debounce_lock:
            if _debounce_timer is not None:
                _debounce_timer.cancel()
            _debounce_timer = threading.Timer(_DEBOUNCE_SECONDS, self._fire)
            _debounce_timer.daemon = True
            _debounce_timer.start()

    def _fire(self) -> None:
        url = self._webhook_url
        headers = {
            "X-Goog-Resource-State": "change",
            "X-Goog-Channel-ID": self._channel_id,
        }
        logger.info("localwatch: POST %s", url)
        try:
            self._post_with_retry(url, headers)
        except httpx.ConnectError:
            logger.exception("localwatch: POST %s failed after retries", url)

    @retry(
        retry=retry_if_exception_type(httpx.ConnectError),
        stop=stop_after_attempt(30),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    )
    def _post_with_retry(self, url: str, headers: dict) -> None:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, headers=headers)
        logger.info("localwatch: POST %s → %d", url, resp.status_code)
