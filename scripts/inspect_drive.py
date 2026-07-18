#!/usr/bin/env python3
"""Diagnostic: inspect the watched folder and its contents.

Uses ``WATCH_FOLDER_ID`` from .env for the folder ID.

Usage::

    pipenv run python scripts/inspect_drive.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

from webhook.config import settings
from webhook.integration.drive import connect, get_file_metadata, list_folder_files

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    folder_id = settings.WATCH_FOLDER_ID
    if not folder_id:
        print("ERROR: WATCH_FOLDER_ID is not set in .env")
        sys.exit(1)

    print(f"Watched folder ID: {folder_id}")

    drive = connect()

    # --- folder metadata ---
    try:
        folder = await get_file_metadata(drive, folder_id)
        print(f"Folder name:    {folder.get('name')}")
        print(f"Owners:         {folder.get('owners')}")
        print(f"Shared:         {folder.get('shared')}")
        print(f"Created:        {folder.get('createdTime')}")
        print(f"Modified:       {folder.get('modifiedTime')}")
    except Exception as exc:
        print(f"ERROR getting folder metadata: {exc}")

    # --- list files ---
    print()
    print("--- Files in folder ---")
    try:
        files = await list_folder_files(drive, folder_id)
    except Exception as exc:
        print(f"ERROR listing files: {exc}")
        sys.exit(1)

    if not files:
        print("NO FILES FOUND. Possible causes:")
        print("  1. Folder is empty")
        print("  2. Service account doesn't have access to files inside")
        print("  3. The folder ID is incorrect")
    else:
        for f in files:
            print(f"  {f['id']}  name={f['name']}")


if __name__ == "__main__":
    asyncio.run(main())
