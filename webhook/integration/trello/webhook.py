"""Trello webhook lifecycle — register, store, sync, and clean up.

Manages one webhook per dashboard board.  Webhook state is persisted in
Firestore under ``trello_webhooks/{dashboard-name}``.  Board data lives in
``dashboards/{dashboard-name}`` (populated by ev-dashboard).
"""

import logging
from datetime import UTC, datetime

from httpx import AsyncClient
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from webhook import db
from webhook.config import settings

logger = logging.getLogger(__name__)

TRELLO_API_BASE = "https://api.trello.com/1"

DASHBOARDS_COLLECTION = "dashboards"
WEBHOOKS_COLLECTION = "trello_webhooks"


class TrelloWebhookData(BaseModel):
    """Stored webhook record for a single dashboard."""

    webhook_id: str
    dashboard_name: str = ""
    description: str = ""
    callback_url: str = ""
    board_id: str = ""
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


# --- Low-level Trello API ----------------------------------------------------


def _auth_params() -> dict[str, str]:
    return {"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_TOKEN}


async def list_webhooks() -> list[dict]:
    """GET /1/tokens/{token}/webhooks"""
    params = _auth_params()
    url = f"{TRELLO_API_BASE}/tokens/{settings.TRELLO_API_TOKEN}/webhooks"

    async with AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        logger.info("list_webhooks: %d webhooks returned", len(data))
        return data


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
async def register_webhook(
    callback_url: str, board_id: str, description: str = "aibiz-webhook"
) -> dict:
    """POST /1/webhooks — retries with backoff for tunnel warm-up."""
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
        if resp.is_error:
            logger.error(
                "register_webhook: Trello returned %d: %s",
                resp.status_code,
                resp.text,
            )
        resp.raise_for_status()
        data = resp.json()
        logger.info(
            "register_webhook: id=%s callback=%s", data.get("id"), callback_url
        )
        return data


async def delete_webhook(webhook_id: str) -> bool:
    """DELETE /1/webhooks/{id}"""
    params = _auth_params()

    async with AsyncClient() as client:
        resp = await client.delete(
            f"{TRELLO_API_BASE}/webhooks/{webhook_id}", params=params
        )
        resp.raise_for_status()
        logger.info("delete_webhook: deleted %s", webhook_id)
        return True


# --- Stored webhook helpers --------------------------------------------------


async def get_dashboard_webhook(dashboard_name: str) -> TrelloWebhookData | None:
    """Return stored webhook for *dashboard_name*, or None."""
    doc = (await db.get_doc(WEBHOOKS_COLLECTION, dashboard_name)).get()
    if not doc.exists:
        return None
    return TrelloWebhookData(**doc.to_dict())


async def _store_webhook(dashboard_name: str, result: dict) -> None:
    """Persist a Trello webhook registration result to Firestore."""
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    await db.update_doc(
        WEBHOOKS_COLLECTION,
        dashboard_name,
        {
            "webhook_id": result.get("id", ""),
            "dashboard_name": dashboard_name,
            "description": result.get("description", ""),
            "callback_url": result.get("callbackURL", settings.TRELLO_WEBHOOK_URL),
            "board_id": result.get("idModel", ""),
            "active": result.get("active", True),
            "updated_at": now_iso,
        },
    )


async def _remove_webhook(dashboard_name: str) -> None:
    """Delete a stored webhook from Firestore."""
    db_client = await db.connect()
    db_client.collection(WEBHOOKS_COLLECTION).document(dashboard_name).delete()


# --- Dashboard webhook lifecycle ---------------------------------------------


async def register_dashboard_webhook(dashboard_name: str, board_id: str) -> str:
    """Register a Trello webhook for *board_id* and store the record.

    Returns the Trello webhook ID.
    """
    logger.info(
        "register_dashboard_webhook: dashboard=%s board=%s",
        dashboard_name,
        board_id,
    )

    result = await register_webhook(
        callback_url=settings.TRELLO_WEBHOOK_URL,
        board_id=board_id,
        description=f"aibiz-{dashboard_name}",
    )

    await _store_webhook(dashboard_name, result)
    logger.info(
        "register_dashboard_webhook: stored webhook_id=%s dashboard=%s",
        result.get("id"),
        dashboard_name,
    )
    return result["id"]


async def sync_dashboard_webhooks() -> dict[str, str]:
    """Ensure a Trello webhook exists for every dashboard in Firestore.

    - Registers new webhooks for dashboards without one.
    - Replaces webhooks whose stored ``board_id`` no longer matches.
    - Deletes webhooks for dashboards that no longer exist.

    Returns a summary dict: ``{added, replaced, removed, unchanged}``.
    """
    dashboards = await db.list_collection(DASHBOARDS_COLLECTION)
    stored_hooks = {
        wh["id"]: wh
        for wh in await db.list_collection(WEBHOOKS_COLLECTION)
    }

    board_ids = {d["id"]: d for d in dashboards}
    added = replaced = removed = unchanged = 0

    # Register / replace
    for dashboard_name, dashboard in board_ids.items():
        board = dashboard.get("board", {})
        current_board_id = board.get("id", "") if isinstance(board, dict) else ""

        if not current_board_id:
            continue

        stored = stored_hooks.pop(dashboard_name, None)
        if stored is None:
            await register_dashboard_webhook(dashboard_name, current_board_id)
            added += 1
        elif stored.get("board_id") != current_board_id:
            logger.info(
                "sync_dashboard_webhooks: board_id changed for %s — replacing webhook",
                dashboard_name,
            )
            try:
                await delete_webhook(stored["webhook_id"])
            except Exception:
                logger.exception("Failed to delete stale webhook %s", stored["webhook_id"])
            await register_dashboard_webhook(dashboard_name, current_board_id)
            replaced += 1
        else:
            unchanged += 1

    # Remove stale webhooks (dashboards that no longer exist)
    for dashboard_name, stored in stored_hooks.items():
        logger.info(
            "sync_dashboard_webhooks: removing webhook for deleted dashboard %s",
            dashboard_name,
        )
        try:
            await delete_webhook(stored["webhook_id"])
        except Exception:
            logger.exception("Failed to delete webhook %s", stored["webhook_id"])
        await _remove_webhook(dashboard_name)
        removed += 1

    summary = {"added": added, "replaced": replaced, "removed": removed, "unchanged": unchanged}
    logger.info("sync_dashboard_webhooks: %s", summary)
    return summary


# --- Sanity check for POST /trello/register ----------------------------------


async def sanity_check_and_store(dashboard_name: str, board_id: str, board_name: str) -> bool:
    """Compare incoming board data with Firestore ``dashboards/{name}``.

    If the stored data differs (or is missing), store the incoming data.
    Returns ``True`` if Firestore was updated.
    """
    stored = await db.get_doc_data(DASHBOARDS_COLLECTION, dashboard_name)
    stored_board = stored.get("board", {}) if stored else {}
    stored_id = stored_board.get("id", "") if isinstance(stored_board, dict) else ""
    stored_name = stored_board.get("name", "") if isinstance(stored_board, dict) else ""

    if stored_id == board_id and stored_name == board_name:
        logger.info("sanity_check: no change for dashboard=%s", dashboard_name)
        return False

    logger.info(
        "sanity_check: updating dashboard=%s board_id=%s board_name=%s",
        dashboard_name,
        board_id,
        board_name,
    )
    await db.update_doc(
        DASHBOARDS_COLLECTION,
        dashboard_name,
        {"board": {"id": board_id, "name": board_name}},
    )
    return True
