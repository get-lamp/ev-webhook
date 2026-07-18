import logging
from datetime import UTC, datetime

from httpx import AsyncClient
from pydantic import BaseModel

from webhook import db
from webhook.config import settings

logger = logging.getLogger(__name__)

TRELLO_API_BASE = "https://api.trello.com/1"

# Firestore collection/doc for stored webhook state
TRELLO_WEBHOOK_COLLECTION = "watch"
TRELLO_WEBHOOK_DOC = "trello_webhook"


class TrelloWebhookData(BaseModel):
    webhook_id: str
    description: str = ""
    callback_url: str = ""
    board_id: str = ""
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Low-level Trello API ----------------------------------------------------


def _auth_params() -> dict[str, str]:
    """Return the key and token query params required by every Trello API call."""
    return {"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_SECRET}


async def list_webhooks() -> list[dict]:
    """List all webhooks for the configured API token.

    GET /1/tokens/{token}/webhooks
    """
    params = _auth_params()
    url = f"{TRELLO_API_BASE}/tokens/{settings.TRELLO_API_SECRET}/webhooks"

    async with AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.info("list_webhooks: %d webhooks returned", len(data))
        return data


async def create_webhook(
    callback_url: str, board_id: str, description: str = "aibiz-webhook"
) -> dict:
    """Register a new Trello webhook.

    POST /1/webhooks
    """
    params = _auth_params()
    body = {
        "description": description,
        "callbackURL": callback_url,
        "idModel": board_id,
    }

    async with AsyncClient() as client:
        resp = await client.post(
            f"{TRELLO_API_BASE}/webhooks", params=params, json=body
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("create_webhook: id=%s callback=%s", data.get("id"), callback_url)
        return data


async def delete_webhook(webhook_id: str) -> bool:
    """Delete a Trello webhook by its id.

    DELETE /1/webhooks/{id}
    """
    params = _auth_params()

    async with AsyncClient() as client:
        resp = await client.delete(
            f"{TRELLO_API_BASE}/webhooks/{webhook_id}", params=params
        )
        resp.raise_for_status()
        logger.info("delete_webhook: deleted %s", webhook_id)
        return True


# --- Webhook lifecycle (check → store) ---------------------------------------


async def get_trello_webhook_data() -> TrelloWebhookData | None:
    """Return stored Trello webhook data from Firestore, or None."""
    doc = (await db.get_doc(TRELLO_WEBHOOK_COLLECTION, TRELLO_WEBHOOK_DOC)).get()

    if not doc.exists:
        return None

    return TrelloWebhookData(**doc.to_dict())


async def webhook_exists_in_trello(callback_url: str) -> bool:
    """Check Trello's API for an existing webhook matching *callback_url*."""
    try:
        webhooks = await list_webhooks()
    except Exception:
        logger.exception("webhook_exists_in_trello: list_webhooks failed")
        return False

    for wh in webhooks:
        if wh.get("callbackURL") == callback_url:
            logger.info(
                "webhook_exists_in_trello: found existing webhook id=%s",
                wh.get("id"),
            )
            return True

    return False


async def create_trello_webhook() -> bool:
    """Create a Trello webhook and store the result in Firestore.

    Returns True on success, False on failure.
    """
    callback_url = f"{settings.WEBHOOK_URL.rstrip('/')}/webhooks/trello/updated"

    logger.info(
        "create_trello_webhook: board=%s callback=%s",
        settings.TRELLO_BOARD_ID,
        callback_url,
    )

    try:
        result = await create_webhook(
            callback_url=callback_url,
            board_id=settings.TRELLO_BOARD_ID,
        )
    except Exception:
        logger.exception("create_trello_webhook: API call failed")
        return False

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    await db.update_doc(
        TRELLO_WEBHOOK_COLLECTION,
        TRELLO_WEBHOOK_DOC,
        {
            "webhook_id": result.get("id", ""),
            "description": result.get("description", ""),
            "callback_url": result.get("callbackURL", callback_url),
            "board_id": result.get("idModel", settings.TRELLO_BOARD_ID),
            "active": result.get("active", True),
            "updated_at": now_iso,
        },
    )

    logger.info("create_trello_webhook: stored webhook id=%s", result.get("id"))
    return True
