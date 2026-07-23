import logging

from webhook import routes
from webhook.config import settings
from webhook.integration import pubsub
from webhook.integration.drive import connect
from webhook.integration.trello import sync_dashboard_webhooks
from webhook.integration.watch import create_watch_channel

logger = logging.getLogger(__name__)


def routing(app):
    # register HTTP routes
    app.include_router(routes.router)
    app.include_router(routes.router_drive)
    app.include_router(routes.router_trello)


async def drive_watch():
    # --- Ensure PubSub emulator topics exist ---
    await pubsub.ensure_topics()

    # --- Drive drive_watch channel ---
    cnx = connect()

    await create_watch_channel(
        cnx, settings.DRIVE_WEBHOOK_URL, settings.WATCH_FOLDER_ID
    )


async def trello_watch():
    if settings.ENVIRONMENT == "local" and not settings.CLOUDFLARE_TUNNEL_ENABLED:
        logger.info("trello_watch: skipping — ENVIRONMENT is local and tunnel disabled")
        return

    logger.info("trello_watch: syncing dashboard webhooks")
    result = await sync_dashboard_webhooks()
    logger.info("trello_watch: sync complete — %s", result)
