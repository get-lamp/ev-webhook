import os
import uuid
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from google.cloud import pubsub_v1
from httpx import ASGITransport, AsyncClient

from webhook.main import app

TEST_PROJECT = "test-project"
TOPICS = ("drive-updated",)


def _require_emulator() -> str:
    host = os.environ.get("PUBSUB_EMULATOR_HOST", "")
    if not host:
        pytest.skip("PUBSUB_EMULATOR_HOST not set — pubsub emulator not available")
    return host


# --- Emulator setup (session scope) -----------------------------------------


@pytest.fixture(scope="session")
def pubsub_emulator() -> Generator[str, None, None]:
    """Verify the emulator is reachable and create required topics once per session."""
    host = _require_emulator()

    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    # Ensure topics exist
    existing = {
        t.name for t in publisher.list_topics(project=f"projects/{TEST_PROJECT}")
    }
    for topic in TOPICS:
        topic_path = publisher.topic_path(TEST_PROJECT, topic)
        if topic_path not in existing:
            publisher.create_topic(name=topic_path)

    # Delete any left-over subscriptions from a previous run
    for sub in subscriber.list_subscriptions(project=f"projects/{TEST_PROJECT}"):
        subscriber.delete_subscription(subscription=sub.name)

    yield host


# --- Per-test subscription helper -------------------------------------------


class PubsubHelper:
    """Create a pull subscription before a test and pull messages after."""

    def __init__(self, project: str, topic: str) -> None:
        self.project = project
        self.topic = topic
        self.subscription_id = f"test-{topic}-{uuid.uuid4().hex[:8]}"
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(
            project, self.subscription_id
        )

        topic_path = pubsub_v1.PublisherClient().topic_path(project, topic)
        self.subscriber.create_subscription(
            name=self.subscription_path, topic=topic_path
        )

    def __enter__(self) -> "PubsubHelper":
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()

    def pull(self, max_messages: int = 10) -> list:
        """Pull messages from the subscription and ack them.

        Uses ``return_immediately=True`` so the call does not block when
        no messages have been published (e.g. unchanged-file tests).
        """
        response = self.subscriber.pull(
            subscription=self.subscription_path,
            max_messages=max_messages,
            return_immediately=True,
        )
        ack_ids = [msg.ack_id for msg in response.received_messages]
        if ack_ids:
            self.subscriber.acknowledge(
                subscription=self.subscription_path, ack_ids=ack_ids
            )
        return response.received_messages

    def cleanup(self) -> None:
        try:
            self.subscriber.delete_subscription(subscription=self.subscription_path)
        except Exception:
            pass


# --- PubSub helper fixture --------------------------------------------------


@pytest.fixture
def pubsub_helper() -> Generator[PubsubHelper, None, None]:
    """Yield a PubsubHelper for ``drive-updated``, cleaning up afterwards."""
    with PubsubHelper(TEST_PROJECT, "drive-updated") as helper:
        yield helper


# --- App client -------------------------------------------------------------


@pytest_asyncio.fixture
async def client(pubsub_emulator: str) -> AsyncGenerator[AsyncClient, None]:
    os.environ.setdefault("PUBSUB_EMULATOR_HOST", pubsub_emulator)
    with (
        patch("webhook.setup.watch", new_callable=AsyncMock),
        patch("webhook.config.settings.GCP_PROJECT_ID", TEST_PROJECT),
        patch("webhook.integration.pubsub.settings.GCP_PROJECT_ID", TEST_PROJECT),
    ):
        async with LifespanManager(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
