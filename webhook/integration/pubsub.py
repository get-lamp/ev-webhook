import asyncio
import json
import logging
import time

from google.cloud import pubsub_v1
from pydantic import BaseModel

from webhook.config import settings
from webhook.schemas.drive import DriveUpdatedTopicSchema

logger = logging.getLogger(__name__)


async def ensure_topics() -> None:
    """No-op in production — topics are managed by Terraform."""


async def _publish(
    topic_name: str, payload: BaseModel, attributes: dict | None = None
) -> int:
    """Publish a JSON message to a PubSub topic. Returns 1 on success, 0 if skipped."""
    if not settings.GCP_PROJECT_ID:
        logger.warning(
            "_publish: GCP_PROJECT_ID not set — cannot publish to %s", topic_name
        )
        return 0

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.GCP_PROJECT_ID, topic_name)

    attrs = attributes or {}
    attrs.setdefault("published_at", str(int(time.time())))

    payload_bytes = payload.model_dump_json(exclude_none=True).encode()
    future = publisher.publish(topic_path, payload_bytes, **attrs)
    await asyncio.to_thread(future.result)
    logger.info(
        "_publish: topic=%s attrs=%s payload=%s",
        topic_name,
        attrs,
        payload.model_dump(),
    )
    return 1


# --- Drive file events (publish + cache update) ------------------------------


def _make_entry(name: str, md5: str) -> dict:
    return {"name": name, "md5": md5}


async def publish_drive_file_added(
    file_id: str, name: str, folder_id: str, md5: str, cache: dict
) -> None:
    """Handle an added file: publish event and record in the cache."""
    await _publish(
        "drive-updated",
        DriveUpdatedTopicSchema(
            file_id=file_id,
            name=name,
            folder_id=folder_id,
            event="file_added",
        ),
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
    """Handle a removed file: publish event and drop from the cache."""
    name = cached_name or fallback_name
    await _publish(
        "drive-updated",
        DriveUpdatedTopicSchema(
            file_id=file_id,
            name=name,
            folder_id=folder_id,
            event="file_removed",
        ),
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
    """Handle a renamed file: publish event and update the cache."""
    await _publish(
        "drive-updated",
        DriveUpdatedTopicSchema(
            file_id=file_id,
            old_name=old_name,
            new_name=new_name,
            folder_id=folder_id,
            event="file_renamed",
        ),
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
    """Handle an updated file: publish event and update the hash in cache."""
    await _publish(
        "drive-updated",
        DriveUpdatedTopicSchema(
            file_id=file_id,
            name=name,
            folder_id=folder_id,
            event="file_updated",
        ),
        {"event": "drive_file_updated", "file_id": file_id},
    )
    cache[file_id]["md5"] = md5
    logger.info("publish_drive_file_updated: file_id=%s name=%s", file_id, name)


# --- Trello events -----------------------------------------------------------


async def push_trello_updated(body: dict) -> int:
    """Publish a Trello webhook payload to PubSub."""
    if not settings.GCP_PROJECT_ID:
        logger.warning("trello_updated: GCP_PROJECT_ID not set — cannot publish")
        return 0

    publisher = pubsub_v1.PublisherClient()
    topic = publisher.topic_path(settings.GCP_PROJECT_ID, "trello-board-updated")
    payload = json.dumps(body).encode()

    future = publisher.publish(topic, payload, event="trello_webhook")
    await asyncio.to_thread(future.result)
    logger.info("Published trello webhook event")
    return 1
