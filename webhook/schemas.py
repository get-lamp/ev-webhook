"""Pydantic schemas for PubSub message payloads."""

from typing import Literal

from pydantic import BaseModel


class DriveUpdatedTopicSchema(BaseModel):
    """Payload published to the ``drive-updated`` topic."""

    file_id: str
    folder_id: str
    event: Literal["file_added", "file_removed", "file_renamed"]

    # file_added / file_removed
    name: str | None = None

    # file_renamed
    old_name: str | None = None
    new_name: str | None = None
