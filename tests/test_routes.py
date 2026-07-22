import json
from unittest.mock import MagicMock, call, patch

import pytest
from httpx import AsyncClient

from tests.conftest import NatsHelper

# --- Sample Drive changes.list responses ------------------------------------

CHANGE_ADDED = {
    "changes": [
        {
            "fileId": "abc123",
            "removed": False,
            "file": {"id": "abc123", "name": "new_file.txt", "md5Checksum": "abc111"},
        }
    ],
    "newStartPageToken": "token-2",
}

CHANGE_REMOVED = {
    "changes": [
        {
            "fileId": "def456",
            "removed": True,
            "file": {"id": "def456", "name": "old_file.txt", "md5Checksum": "def222"},
        }
    ],
    "newStartPageToken": "token-3",
}

CHANGE_RENAMED = {
    "changes": [
        {
            "fileId": "ghi789",
            "removed": False,
            "file": {
                "id": "ghi789",
                "name": "renamed_file.txt",
                "md5Checksum": "ghi333",
            },
        }
    ],
    "newStartPageToken": "token-4",
}

CHANGE_UPDATED = {
    "changes": [
        {
            "fileId": "jkl012",
            "removed": False,
            "file": {
                "id": "jkl012",
                "name": "existing_file.txt",
                "md5Checksum": "jkl444",
            },
        }
    ],
    "newStartPageToken": "token-5",
}

CHANGE_UNCHANGED = {
    "changes": [
        {
            "fileId": "mno345",
            "removed": False,
            "file": {
                "id": "mno345",
                "name": "unchanged_file.txt",
                "md5Checksum": "mno555",
            },
        }
    ],
    "newStartPageToken": "token-6",
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
async def test_file_added(client: AsyncClient, nats_helper: NatsHelper) -> None:
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
        assert response.json()["status"] == "ok"

        msgs = await nats_helper.pull()
        assert len(msgs) == 1
        data = json.loads(msgs[0].data)
        assert data == {
            "file_id": "abc123",
            "name": "new_file.txt",
            "folder_id": FOLDER_ID,
            "event": "file_added",
        }
        assert msgs[0].headers["event"] == "drive_file_added"
        assert msgs[0].headers["file_id"] == "abc123"

        assert mock_update_doc.call_args_list[0] == call(
            "watch",
            "drive_file_state",
            {"abc123": {"name": "new_file.txt", "md5": "abc111"}},
            replace=True,
        )


# --- Drive: file removed -----------------------------------------------------


@pytest.mark.asyncio
async def test_file_removed(client: AsyncClient, nats_helper: NatsHelper) -> None:
    with (
        patch("webhook.integration.drive.connect") as mock_connect,
        patch("webhook.integration.drive.list_changes") as mock_list_changes,
        patch("webhook.db.get_doc_data") as mock_get_doc,
        patch("webhook.db.update_doc") as mock_update_doc,
    ):
        mock_connect.return_value = MagicMock()
        mock_list_changes.return_value = CHANGE_REMOVED
        mock_get_doc.side_effect = [
            WATCH_CHANNEL_DATA,
            {"def456": {"name": "old_file.txt", "md5": "def222"}},
        ]
        mock_update_doc.return_value = None

        response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        msgs = await nats_helper.pull()
        assert len(msgs) == 1
        data = json.loads(msgs[0].data)
        assert data == {
            "file_id": "def456",
            "name": "old_file.txt",
            "folder_id": FOLDER_ID,
            "event": "file_removed",
        }
        assert msgs[0].headers["event"] == "drive_file_removed"

        assert mock_update_doc.call_args_list[0] == call(
            "watch", "drive_file_state", {}, replace=True
        )


# --- Drive: file renamed -----------------------------------------------------


@pytest.mark.asyncio
async def test_file_renamed(client: AsyncClient, nats_helper: NatsHelper) -> None:
    with (
        patch("webhook.integration.drive.connect") as mock_connect,
        patch("webhook.integration.drive.list_changes") as mock_list_changes,
        patch("webhook.db.get_doc_data") as mock_get_doc,
        patch("webhook.db.update_doc") as mock_update_doc,
    ):
        mock_connect.return_value = MagicMock()
        mock_list_changes.return_value = CHANGE_RENAMED
        mock_get_doc.side_effect = [
            WATCH_CHANNEL_DATA,
            {"ghi789": {"name": "old_name.txt", "md5": "ghi333"}},
        ]
        mock_update_doc.return_value = None

        response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        msgs = await nats_helper.pull()
        assert len(msgs) == 1
        data = json.loads(msgs[0].data)
        assert data == {
            "file_id": "ghi789",
            "old_name": "old_name.txt",
            "new_name": "renamed_file.txt",
            "folder_id": FOLDER_ID,
            "event": "file_renamed",
        }
        assert msgs[0].headers["event"] == "drive_file_renamed"

        assert mock_update_doc.call_args_list[0] == call(
            "watch",
            "drive_file_state",
            {"ghi789": {"name": "renamed_file.txt", "md5": "ghi333"}},
            replace=True,
        )


# --- Drive: file updated (content changed, hash differs) ---------------------


@pytest.mark.asyncio
async def test_file_updated(client: AsyncClient, nats_helper: NatsHelper) -> None:
    with (
        patch("webhook.integration.drive.connect") as mock_connect,
        patch("webhook.integration.drive.list_changes") as mock_list_changes,
        patch("webhook.db.get_doc_data") as mock_get_doc,
        patch("webhook.db.update_doc") as mock_update_doc,
    ):
        mock_connect.return_value = MagicMock()
        mock_list_changes.return_value = CHANGE_UPDATED
        mock_get_doc.side_effect = [
            WATCH_CHANNEL_DATA,
            {"jkl012": {"name": "existing_file.txt", "md5": "oldhash"}},
        ]
        mock_update_doc.return_value = None

        response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "added": 0,
            "removed": 0,
            "renamed": 0,
            "updated": 1,
        }

        msgs = await nats_helper.pull()
        assert len(msgs) == 1
        data = json.loads(msgs[0].data)
        assert data == {
            "file_id": "jkl012",
            "name": "existing_file.txt",
            "folder_id": FOLDER_ID,
            "event": "file_updated",
        }
        assert msgs[0].headers["event"] == "drive_file_updated"
        assert msgs[0].headers["file_id"] == "jkl012"

        assert mock_update_doc.call_args_list[0] == call(
            "watch",
            "drive_file_state",
            {"jkl012": {"name": "existing_file.txt", "md5": "jkl444"}},
            replace=True,
        )


# --- Drive: file unchanged (same name and hash) ------------------------------


@pytest.mark.asyncio
async def test_file_unchanged(client: AsyncClient, nats_helper: NatsHelper) -> None:
    with (
        patch("webhook.integration.drive.connect") as mock_connect,
        patch("webhook.integration.drive.list_changes") as mock_list_changes,
        patch("webhook.db.get_doc_data") as mock_get_doc,
        patch("webhook.db.update_doc") as mock_update_doc,
    ):
        mock_connect.return_value = MagicMock()
        mock_list_changes.return_value = CHANGE_UNCHANGED
        mock_get_doc.side_effect = [
            WATCH_CHANNEL_DATA,
            {"mno345": {"name": "unchanged_file.txt", "md5": "mno555"}},
        ]
        mock_update_doc.return_value = None

        response = await client.post("/drive/updated", headers=DRIVE_HEADERS)

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "added": 0,
            "removed": 0,
            "renamed": 0,
            "updated": 0,
        }

        msgs = await nats_helper.pull()
        assert len(msgs) == 0

        assert mock_update_doc.call_args_list[0] == call(
            "watch",
            "drive_file_state",
            {"mno345": {"name": "unchanged_file.txt", "md5": "mno555"}},
            replace=True,
        )
