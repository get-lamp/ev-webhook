import logging
import time
import uuid
from datetime import UTC, datetime

from googleapiclient.errors import HttpError
from pydantic import BaseModel

from webhook import db as db

logger = logging.getLogger(__name__)


RENEWAL_WINDOW_SECONDS = 3600  # renew if < 1 h until expiry
WATCH_TTL_SECONDS = 604800  # 7 days (Drive default max)


class WatchChannelData(BaseModel):
    channel_id: str
    resource_id: str = ""
    resource_uri: str = ""
    expiration: int = 0  # unix millis
    page_token: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


async def get_watcher_channel_data():

    doc = (await db.get_doc("watch", "drive_channel")).get()

    if not doc.exists:
        return False

    return WatchChannelData(**doc.to_dict())


def channel_expired(channel_data: WatchChannelData):

    now_ms = int(time.time() * 1000)
    renewal_boundary_ms = now_ms + (RENEWAL_WINDOW_SECONDS * 1000)

    # remaining_s = (expiration_ms - now_ms) // 1000
    return channel_data["expiration"] > renewal_boundary_ms


async def create_watch_channel(drive, webhook_url, watch_folder_id) -> bool:
    new_channel_id = str(uuid.uuid4())
    webhook_url = f"{webhook_url.rstrip('/')}/webhooks/drive-updated"
    now_ms = int(time.time() * 1000)

    logger.info(
        "renew_drive_watch: watching folder %s drive_watch=%s",
        watch_folder_id,
        webhook_url,
    )

    try:
        channel = (
            drive.changes()
            .watch(
                fileId=watch_folder_id,
                body={
                    "id": new_channel_id,
                    "type": "web_hook",
                    "address": webhook_url,
                    "expiration": str(now_ms + WATCH_TTL_SECONDS * 1000),
                },
            )
            .execute()
        )

    except HttpError:
        logger.exception("renew_drive_watch: changes().watch() failed")
        return False

    new_resource_id = channel.get("resourceId", "")
    new_expiration_ms = int(channel.get("expiration", 0))

    logger.info(
        "renew_drive_watch: new channel created id=%s resource=%s expiration=%d",
        new_channel_id,
        new_resource_id,
        new_expiration_ms,
    )

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    await db.update_doc(
        "watch",
        "drive_channel",
        {
            "channel_id": new_channel_id,
            "resource_id": new_resource_id,
            "resource_uri": channel.get("resourceUri", channel.get("resource_uri", "")),
            "expiration": new_expiration_ms,
            "updated_at": now_iso,
        },
    )

    return True


async def stop_watch_channel(drive, channel_id) -> bool:
    try:
        drive.channels().stop(
            body={"id": channel_id, "resourceId": channel_id}
        ).execute()
        logger.info("renew_drive_watch: stopped old channel %s", channel_id)
        return True

    except HttpError as exc:
        # Channel may already be expired — that's fine
        logger.info(
            "renew_drive_watch: old channel %s stop returned: %s", channel_id, exc
        )

    return False
