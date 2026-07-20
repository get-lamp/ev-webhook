"""Local PubSub implementation — direct HTTP push when running with the emulator.

The PubSub emulator does not support push subscriptions, so in local dev
we POST drive events directly to the workshop service instead of going
through the emulator's publish/subscribe cycle.

Topic creation is still done against the emulator so that anything pulling
from it (e.g. tests) finds the expected resources.
"""

import json
import logging
import os

import httpx
from pydantic import BaseModel

from webhook.config import settings
from webhook.schemas import DriveUpdatedTopicSchema

logger = logging.getLogger(__name__)

PUBSUB_TOPICS = ["drive-updated", "trello-board-updated"]


async def ensure_topics() -> None:
    """Create PubSub topics in the emulator so they exist for tests / pull subscribers."""
    emulator_host = os.environ.get("PUBSUB_EMULATOR_HOST")
    if not emulator_host:
        return

    project = settings.GCP_PROJECT_ID
    async with httpx.AsyncClient(timeout=5) as client:
        for topic in PUBSUB_TOPICS:
            url = f"http://{emulator_host}/v1/projects/{project}/topics/{topic}"
            try:
                resp = await client.put(url)
                logger.info("ensure_topics: PUT %s → %d", url, resp.status_code)
            except Exception:
                logger.exception("ensure_topics: PUT %s failed", url)


# --- Direct HTTP push to workshop -----------------------------------------


def _post_to_workshop(payload: BaseModel) -> None:
    """POST a drive-event payload directly to the workshop service."""
    push_url = settings.TOPIC_BLUEPRINT_PUSH_URL
    if not push_url:
        logger.warning("_post_to_workshop: TOPIC_BLUEPRINT_PUSH_URL not set")
        return

    body = payload.model_dump_json(exclude_none=True)
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(push_url, content=body, headers={"Content-Type": "application/json"})
        logger.info("_post_to_workshop: POST %s → %d", push_url, resp.status_code)
    except Exception:
        logger.exception("_post_to_workshop: POST %s failed", push_url)


# --- Drive file events (push to workshop + cache update) ------------------


def _make_entry(name: str, md5: str) -> dict:
    return {"name": name, "md5": md5}


def publish_drive_file_added(
    file_id: str, name: str, folder_id: str, md5: str, cache: dict
) -> None:
    payload = DriveUpdatedTopicSchema(
        file_id=file_id, name=name, folder_id=folder_id, event="file_added"
    )
    _post_to_workshop(payload)
    cache[file_id] = _make_entry(name, md5)
    logger.info("publish_drive_file_added: file_id=%s name=%s", file_id, name)


def publish_drive_file_removed(
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
    _post_to_workshop(payload)
    cache.pop(file_id, None)
    logger.info("publish_drive_file_removed: file_id=%s name=%s", file_id, name)


def publish_drive_file_renamed(
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
    _post_to_workshop(payload)
    cache[file_id] = _make_entry(new_name, md5)
    logger.info(
        "publish_drive_file_renamed: file_id=%s %s → %s",
        file_id,
        old_name,
        new_name,
    )


def publish_drive_file_updated(
    file_id: str, name: str, folder_id: str, md5: str, cache: dict
) -> None:
    payload = DriveUpdatedTopicSchema(
        file_id=file_id, name=name, folder_id=folder_id, event="file_updated"
    )
    _post_to_workshop(payload)
    cache[file_id]["md5"] = md5
    logger.info("publish_drive_file_updated: file_id=%s name=%s", file_id, name)


# --- Trello events --------------------------------------------------------


def push_trello_updated(body: dict) -> int:
    """No-op in local dev — Trello can't reach us."""
    logger.info("push_trello_updated: skipped (local dev)")
    return 0
