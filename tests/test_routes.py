import json
from unittest.mock import MagicMock, call, patch

import pytest
from httpx import AsyncClient

from tests.conftest import PubsubHelper

# --- Sample Drive changes.list responses ------------------------------------

CHANGE_ADDED = {
    "changes": [
        {
            "fileId": "abc123",
            "removed": False,
            "file": {"id": "abc123", "name": "new_file.txt"},
        }
    ],
    "newStartPageToken": "token-2",
}

CHANGE_REMOVED = {
    "changes": [
        {
            "fileId": "def456",
            "removed": True,
            "file": {"id": "def456", "name": "old_file.txt"},
        }
    ],
    "newStartPageToken": "token-3",
}

CHANGE_RENAMED = {
    "changes": [
        {
            "fileId": "ghi789",
            "removed": False,
            "file": {"id": "ghi789", "name": "renamed_file.txt"},
        }
    ],
    "newStartPageToken": "token-4",
}

DRIVE_HEADERS = {
    "X-Goog-Resource-State": "change",
    "X-Goog-Channel-ID": "test-channel",
}

WATCH_CHANNEL_DATA = {"page_token": "token-1"}

FOLDER_ID = "1cg46x8WCSerAw2UmGIgHUb_W_oNsGJsV"


# --- Health -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- Drive: file added -------------------------------------------------------


@pytest.mark.asyncio
async def test_file_added(client: AsyncClient) -> None:
    helper = PubsubHelper("test-project", "drive-updated")
    try:
        with (
            patch("webhook.integration.drive.connect") as mock_connect,
            patch("webhook.integration.drive.list_changes") as mock_list_changes,
            patch("webhook.db.get_doc_data") as mock_get_doc,
            patch("webhook.db.update_doc") as mock_update_doc,
        ):
            mock_connect.return_value = MagicMock()
            mock_list_changes.return_value = CHANGE_ADDED
            mock_get_doc.side_effect = [WATCH_CHANNEL_DATA, {}]
            mock_update_doc.return_value = None

            response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # Pull and verify the published PubSub message
            msgs = helper.pull()
            assert len(msgs) == 1
            data = json.loads(msgs[0].message.data)
            assert data == {
                "file_id": "abc123",
                "name": "new_file.txt",
                "folder_id": FOLDER_ID,
                "event": "file_added",
            }
            assert msgs[0].message.attributes["event"] == "drive_file_added"
            assert msgs[0].message.attributes["file_id"] == "abc123"

            # Verify the updated cache was persisted
            assert mock_update_doc.call_args_list[0] == call(
                "watch", "drive_file_state", {"abc123": "new_file.txt"}
            )
    finally:
        helper.cleanup()


# --- Drive: file removed -----------------------------------------------------


@pytest.mark.asyncio
async def test_file_removed(client: AsyncClient) -> None:
    helper = PubsubHelper("test-project", "drive-updated")
    try:
        with (
            patch("webhook.integration.drive.connect") as mock_connect,
            patch("webhook.integration.drive.list_changes") as mock_list_changes,
            patch("webhook.db.get_doc_data") as mock_get_doc,
            patch("webhook.db.update_doc") as mock_update_doc,
        ):
            mock_connect.return_value = MagicMock()
            mock_list_changes.return_value = CHANGE_REMOVED
            mock_get_doc.side_effect = [WATCH_CHANNEL_DATA, {"def456": "old_file.txt"}]
            mock_update_doc.return_value = None

            response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # Pull and verify the published PubSub message
            msgs = helper.pull()
            assert len(msgs) == 1
            data = json.loads(msgs[0].message.data)
            assert data == {
                "file_id": "def456",
                "name": "old_file.txt",
                "folder_id": FOLDER_ID,
                "event": "file_removed",
            }
            assert msgs[0].message.attributes["event"] == "drive_file_removed"

            # Verify the cache had the entry removed
            assert mock_update_doc.call_args_list[0] == call(
                "watch", "drive_file_state", {}
            )
    finally:
        helper.cleanup()


# --- Drive: file renamed -----------------------------------------------------


@pytest.mark.asyncio
async def test_file_renamed(client: AsyncClient) -> None:
    helper = PubsubHelper("test-project", "drive-updated")
    try:
        with (
            patch("webhook.integration.drive.connect") as mock_connect,
            patch("webhook.integration.drive.list_changes") as mock_list_changes,
            patch("webhook.db.get_doc_data") as mock_get_doc,
            patch("webhook.db.update_doc") as mock_update_doc,
        ):
            mock_connect.return_value = MagicMock()
            mock_list_changes.return_value = CHANGE_RENAMED
            mock_get_doc.side_effect = [WATCH_CHANNEL_DATA, {"ghi789": "old_name.txt"}]
            mock_update_doc.return_value = None

            response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            # Pull and verify the published PubSub message
            msgs = helper.pull()
            assert len(msgs) == 1
            data = json.loads(msgs[0].message.data)
            assert data == {
                "file_id": "ghi789",
                "old_name": "old_name.txt",
                "new_name": "renamed_file.txt",
                "folder_id": FOLDER_ID,
                "event": "file_renamed",
            }
            assert msgs[0].message.attributes["event"] == "drive_file_renamed"

            # Verify the cache was updated with the new name
            assert mock_update_doc.call_args_list[0] == call(
                "watch", "drive_file_state", {"ghi789": "renamed_file.txt"}
            )
    finally:
        helper.cleanup()
