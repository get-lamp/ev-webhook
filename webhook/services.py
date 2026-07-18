import logging

from webhook import db
from webhook.integration import drive, pubsub

logger = logging.getLogger(__name__)

FILE_STATE_COLLECTION = "watch"
FILE_STATE_DOC = "drive_file_state"


async def handle_drive_updated(channel_id: str, folder_id: str, state: str) -> dict:
    """Process a Drive push notification.

    1. Fetch changes via ``changes.list`` using the stored page token.
    2. Categorise each change as **added**, **removed**, or **renamed**.
    3. Publish the corresponding PubSub event.
    4. Update the page token and file-name cache in Firestore.
    """
    drive_conn = drive.connect()
    channel_data = await db.get_doc_data("watch", "drive_channel")

    page_token = channel_data.get("page_token", "") if channel_data else ""
    logger.info("handle_drive_updated: state=%s page_token=%s", state, page_token)

    # Fetch changes since the last page token
    changes_resp = await drive.list_changes(drive_conn, page_token or None)
    changes = changes_resp.get("changes", [])
    new_page_token = changes_resp.get("newStartPageToken", page_token)

    if not changes:
        logger.info("handle_drive_updated: no changes to process")
        return {"status": "ok", "processed": 0}

    # Load file-name cache: {file_id: name}
    cache = await db.get_doc_data(FILE_STATE_COLLECTION, FILE_STATE_DOC) or {}

    added = removed = renamed = 0

    for change in changes:
        file_id = change.get("fileId", "")
        removed_flag = change.get("removed", False)
        file_info = change.get("file", {})
        current_name = file_info.get("name", "unknown")
        cached_name = cache.get(file_id)

        if removed_flag:
            pubsub.publish_drive_file_removed(
                file_id, cached_name, current_name, folder_id, cache
            )
            removed += 1

        elif file_id not in cache:
            pubsub.publish_drive_file_added(file_id, current_name, folder_id, cache)
            added += 1

        elif cached_name != current_name:
            pubsub.publish_drive_file_renamed(
                file_id, cached_name, current_name, folder_id, cache
            )
            renamed += 1

        else:
            pubsub.publish_drive_file_unchanged(file_id, current_name, change)

    # Persist updated cache and page token
    await db.update_doc(FILE_STATE_COLLECTION, FILE_STATE_DOC, cache)
    await db.update_doc("watch", "drive_channel", {"page_token": new_page_token})

    logger.info(
        "handle_drive_updated: processed added=%d removed=%d renamed=%d",
        added,
        removed,
        renamed,
    )
    return {
        "status": "ok",
        "added": added,
        "removed": removed,
        "renamed": renamed,
    }
