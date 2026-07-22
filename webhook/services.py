import logging

from webhook import db
from webhook.integration import drive, pubsub

logger = logging.getLogger(__name__)

FILE_STATE_COLLECTION = "watch"
FILE_STATE_DOC = "drive_file_state"


async def handle_drive_updated(channel_id: str, folder_id: str, state: str) -> dict:
    """Process a Drive push notification.

    1. Fetch changes via ``changes.list`` using the stored page token.
    2. Categorise each change as **added**, **removed**, **renamed**, or
       **updated** (content changed, detected by ``md5Checksum``).
    3. Publish the corresponding PubSub event.
    4. Update the page token and cache in Firestore.
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

    # Load cache: {file_id: {"name": str, "md5": str}}
    cache = await db.get_doc_data(FILE_STATE_COLLECTION, FILE_STATE_DOC) or {}

    added = removed = renamed = updated = 0

    for change in changes:
        file_id = change.get("fileId", "")
        removed_flag = change.get("removed", False)
        file_info = change.get("file", {})
        current_name = file_info.get("name", "unknown")
        current_md5 = file_info.get("md5Checksum", "")
        cached_entry = cache.get(file_id)

        if removed_flag:
            cached_name = cached_entry["name"] if cached_entry else None
            await pubsub.publish_drive_file_removed(
                file_id, cached_name, current_name, folder_id, cache
            )
            removed += 1

        elif file_id not in cache:
            await pubsub.publish_drive_file_added(
                file_id, current_name, folder_id, current_md5, cache
            )
            added += 1

        elif cached_entry["name"] != current_name:
            await pubsub.publish_drive_file_renamed(
                file_id,
                cached_entry["name"],
                current_name,
                folder_id,
                current_md5,
                cache,
            )
            renamed += 1

        elif cached_entry["md5"] != current_md5:
            await pubsub.publish_drive_file_updated(
                file_id, current_name, folder_id, current_md5, cache
            )
            updated += 1

        else:
            logger.info(
                "handle_drive_updated: file unchanged: file_id=%s name=%s",
                file_id,
                current_name,
            )

    # Persist updated cache and page token.
    # Replace (not merge) so that cache.pop() removals are actually deleted.
    await db.update_doc(FILE_STATE_COLLECTION, FILE_STATE_DOC, cache, replace=True)
    await db.update_doc("watch", "drive_channel", {"page_token": new_page_token})

    logger.info(
        "handle_drive_updated: processed added=%d removed=%d renamed=%d updated=%d",
        added,
        removed,
        renamed,
        updated,
    )
    return {
        "status": "ok",
        "added": added,
        "removed": removed,
        "renamed": renamed,
        "updated": updated,
    }
