import asyncio
import os
from collections.abc import AsyncGenerator, AsyncIterator
from unittest.mock import AsyncMock, patch

import nats
import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from nats.aio.client import Client as NATSClient

from webhook.main import app

TEST_PROJECT = "test-project"
DEFAULT_NATS_URL = "nats://localhost:4222"


def _require_nats() -> str:
    """Return the NATS URL if a server is reachable, otherwise skip tests."""
    url = os.environ.get("NATS_URL", DEFAULT_NATS_URL)
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_probe_nats(url))
        loop.close()
    except Exception:
        pytest.skip(f"NATS server not reachable at {url}")
    return url


async def _probe_nats(url: str) -> None:
    nc = await nats.connect(url, connect_timeout=3)
    await nc.drain()


# --- NATS server fixture (session scope) ------------------------------------


@pytest.fixture(scope="session")
def nats_server() -> str:
    """Verify NATS is reachable and return the URL."""
    return _require_nats()


# --- NATS test helper -------------------------------------------------------


class NatsHelper:
    """Subscribe to a NATS subject, collect messages, and verify in tests."""

    def __init__(self, subject: str) -> None:
        self.subject = subject
        self._nc: NATSClient | None = None
        self.messages: list = []

    async def __aenter__(self) -> "NatsHelper":
        url = os.environ.get("NATS_URL", DEFAULT_NATS_URL)
        self._nc = await nats.connect(url)
        self._sub = await self._nc.subscribe(self.subject, cb=self._on_message)
        return self

    async def _on_message(self, msg) -> None:
        self.messages.append(msg)

    async def pull(self, timeout: float = 0.5) -> list:
        """Wait briefly for in-flight messages, return collected messages."""
        await asyncio.sleep(timeout)
        return self.messages

    async def __aexit__(self, *args: object) -> None:
        await self._sub.unsubscribe()
        await self._nc.drain()


# --- NATS helper fixture ----------------------------------------------------


@pytest_asyncio.fixture
async def nats_helper() -> AsyncIterator[NatsHelper]:
    """Yield a NatsHelper subscribed to ``drive-updated``."""
    async with NatsHelper("drive-updated") as helper:
        yield helper


# --- App client -------------------------------------------------------------


@pytest_asyncio.fixture
async def client(
    nats_server: str,
) -> AsyncGenerator[AsyncClient, None]:
    os.environ.setdefault("NATS_URL", nats_server)
    with (
        patch("webhook.setup.drive_watch", new_callable=AsyncMock),
        patch("webhook.setup.trello_watch", new_callable=AsyncMock),
        patch("webhook.integration.pubsub.settings.GCP_PROJECT_ID", TEST_PROJECT),
    ):
        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
