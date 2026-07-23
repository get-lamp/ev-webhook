#!/usr/bin/env python3
"""List the active Drive drive_watch channel stored in Firestore.

Usage::

    pipenv run python scripts/list_channels.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

from webhook.integration.watch import get_watcher_channel_data

logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    channel = await get_watcher_channel_data()

    if not channel:
        print("No drive_watch channel found in Firestore (drive_watch/drive_channel).")
        print("The app will create one automatically on startup.")
        sys.exit(1)

    print()
    print("Drive drive_watch channel (from Firestore drive_watch/drive_channel):")
    print(f"  Channel ID:    {channel.channel_id}")
    print(f"  Resource ID:   {channel.resource_id}")
    print(f"  Resource URI:  {channel.resource_uri}")
    print(f"  Expiration:    {channel.expiration}")
    print(f"  Page token:    {channel.page_token}")
    print(f"  Created:       {channel.created_at}")
    print(f"  Updated:       {channel.updated_at}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
