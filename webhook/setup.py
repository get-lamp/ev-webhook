import logging

from webhook import routes
from webhook.config import settings
from webhook.integration.drive import connect
from webhook.integration.trello import (
    create_trello_webhook,
    get_trello_webhook_data,
    webhook_exists_in_trello,
)
from webhook.integration.watch import create_watch_channel

logger = logging.getLogger(__name__)


def routing(app):
    # register HTTP routes
    app.include_router(routes.router)
    app.include_router(routes.router_drive)
    app.include_router(routes.router_trello)


async def watch():
    # --- Drive watch channel ---
    cnx = connect()

    await create_watch_channel(cnx, settings.WEBHOOK_URL, settings.WATCH_FOLDER_ID)

    # --- Trello webhook ---
    stored = await get_trello_webhook_data()

    if stored is not None:
        logger.info("trello_watch: webhook already stored id=%s", stored.webhook_id)
        return

    callback_url = f"{settings.WEBHOOK_URL.rstrip('/')}/webhooks/trello/updated"

    if await webhook_exists_in_trello(callback_url):
        logger.info(
            "trello_watch: webhook exists at Trello but not in Firestore — skipping"
        )
        return

    logger.info("trello_watch: no webhook found — creating")
    ok = await create_trello_webhook()
    logger.info("trello_watch: created=%s", ok)
