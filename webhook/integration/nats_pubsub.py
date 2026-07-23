"""Local NATS pubsub — drop-in replacement for the PubSub emulator.

Uses core NATS (no JetStream) for lightweight fire-and-forget publish.
Subjects auto-create on first publish so ``ensure_topics`` is a no-op.
PubSub attributes become NATS headers (``event``, ``file_id``, ``published_at``).

Subjects
--------
drive-updated         — Drive file change events
trello-board-updated  — Trello webhook events
"""

import json
import logging
import time

import nats

from webhook.config import settings
from webhook.schemas.drive import DriveUpdatedTopicSchema

logger = logging.getLogger(__name__)

# Lazy singleton — connected once at startup and reused.
_client: nats.NATS | None = None


async def _get_client() -> nats.NATS:
    """Return the singleton NATS client, connecting on first call."""
    global _client
    if _client is None or not _client.is_connected:
        _client = await nats.connect(
            settings.NATS_URL,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
        )
        logger.info("NATS connected to %s", settings.NATS_URL)
    return _client


# --- Public API (same signatures as pubsub.py) ------------------------------


async def ensure_topics() -> None:
    """Verify NATS connectivity. Subjects auto-create on publish — no-op."""
    try:
        await _get_client()
        logger.info("ensure_topics: NATS connection OK")
    except Exception:
        logger.exception(
            "ensure_topics: Failed to connect to NATS at %s", settings.NATS_URL
        )


async def _publish(
    subject: str,
    payload_bytes: bytes,
    headers: dict[str, str] | None = None,
) -> int:
    """Publish raw bytes to a NATS subject. Returns 1 on success, 0 if skipped."""
    if not settings.NATS_URL:
        logger.warning("_publish: NATS_URL not set — cannot publish to %s", subject)
        return 0

    hdrs = dict(headers or {})
    hdrs.setdefault("published_at", str(int(time.time())))

    nc = await _get_client()
    await nc.publish(subject, payload_bytes, headers=hdrs)
    logger.info("_publish: subject=%s headers=%s", subject, hdrs)
    return 1


# --- Drive file events (publish + cache update) ------------------------------


def _make_entry(name: str, md5: str) -> dict:
    return {"name": name, "md5": md5}


async def publish_drive_file_added(
    file_id: str, name: str, folder_id: str, md5: str, cache: dict
) -> None:
    payload = DriveUpdatedTopicSchema(
        file_id=file_id, name=name, folder_id=folder_id, event="file_added"
    )
    await _publish(
        "drive-updated",
        payload.model_dump_json(exclude_none=True).encode(),
        {"event": "drive_file_added", "file_id": file_id},
    )
    cache[file_id] = _make_entry(name, md5)
    logger.info("publish_drive_file_added: file_id=%s name=%s", file_id, name)


async def publish_drive_file_removed(
    file_id: str,
    cached_name: str | None,
    fallback_name: str,
    folder_id: str,
    cache: dict,
) -> None:
    name = cached_name or fallback_name
    payload = DriveUpdatedTopicSchema(
        file_id=file_id, name=name, folder_id=folder_id, event="file_removed"
    )
    await _publish(
        "drive-updated",
        payload.model_dump_json(exclude_none=True).encode(),
        {"event": "drive_file_removed", "file_id": file_id},
    )
    cache.pop(file_id, None)
    logger.info("publish_drive_file_removed: file_id=%s name=%s", file_id, name)


async def publish_drive_file_renamed(
    file_id: str,
    old_name: str,
    new_name: str,
    folder_id: str,
    md5: str,
    cache: dict,
) -> None:
    payload = DriveUpdatedTopicSchema(
        file_id=file_id,
        old_name=old_name,
        new_name=new_name,
        folder_id=folder_id,
        event="file_renamed",
    )
    await _publish(
        "drive-updated",
        payload.model_dump_json(exclude_none=True).encode(),
        {"event": "drive_file_renamed", "file_id": file_id},
    )
    cache[file_id] = _make_entry(new_name, md5)
    logger.info(
        "publish_drive_file_renamed: file_id=%s %s → %s",
        file_id,
        old_name,
        new_name,
    )


async def publish_drive_file_updated(
    file_id: str, name: str, folder_id: str, md5: str, cache: dict
) -> None:
    payload = DriveUpdatedTopicSchema(
        file_id=file_id, name=name, folder_id=folder_id, event="file_updated"
    )
    await _publish(
        "drive-updated",
        payload.model_dump_json(exclude_none=True).encode(),
        {"event": "drive_file_updated", "file_id": file_id},
    )
    cache[file_id]["md5"] = md5
    logger.info("publish_drive_file_updated: file_id=%s name=%s", file_id, name)


# --- Trello events -----------------------------------------------------------


async def push_trello_updated(body: dict) -> int:
    """Publish a Trello webhook payload to NATS (now works in local dev)."""
    payload_bytes = json.dumps(body).encode()
    await _publish(
        "trello-board-updated",
        payload_bytes,
        {"event": "trello_webhook"},
    )
    logger.info("push_trello_updated: published to trello-board-updated")
    return 1
