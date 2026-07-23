import logging

from fastapi import APIRouter, Request

from webhook.config import settings
from webhook.integration import pubsub
from webhook.schemas.trello import TrelloWebhookPayload
from webhook.services import handle_drive_updated

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhook", "health"])
router_drive = APIRouter(prefix="/drive", tags=["webhook", "drive"])
router_trello = APIRouter(prefix="/trello", tags=["webhook", "trello"])


@router.get("/health")
async def health_check() -> dict:
    """Liveness check — confirms HTTP is available."""
    return {"status": "ok"}


@router_drive.post("/updated")
async def drive_updated(request: Request) -> dict:
    """Receive a Drive push notification, list files in the watched folder,
    and publish a snapshot to PubSub."""

    folder_id = settings.WATCH_FOLDER_ID
    state = request.headers.get("X-Goog-Resource-State", "")
    channel_id = request.headers.get("X-Goog-Channel-ID", "")

    logger.info(
        "drive_watch request: state=%s folder=%s channel=%s project=%s",
        state,
        folder_id,
        channel_id,
        settings.GCP_PROJECT_ID or "<unset>",
    )

    # files().drive_watch() sends "change" (initial sync) and "update" (content changes).
    if state not in ("change", "update"):
        logger.info(
            "drive_watch: ignoring unhandled state=%s channel=%s", state, channel_id
        )
        return {"status": "ignored", "reason": f"unhandled resource state: {state}"}

    if not folder_id:
        logger.warning("drive_watch drive_watch: WATCHED_FOLDER_ID not set")
        return {"status": "error", "reason": "WATCHED_FOLDER_ID not set"}

    result = await handle_drive_updated(channel_id, folder_id, state)

    return result


@router_trello.head("/updated")
async def acknowledge_webhook(request: Request) -> dict:
    return {"status": "ok"}


@router_trello.post("/updated")
async def trello_updated(request: Request) -> dict:

    """Receive a Trello webhook notification and publish to PubSub."""
    body = await request.json()
    payload = TrelloWebhookPayload(**body)

    action = payload.action
    data = action.data if action else None
    board = data.board if data else None
    card = data.card if data else None
    creator = action.memberCreator if action else None
    model = payload.model

    action_type = action.type if action else "unknown"
    board_id = board.id if board else (model.id if model else "")
    card_id = card.id if card else ""
    member = creator.username if creator else "unknown"

    logger.info(
        "trello_updated: type=%s board=%s card=%s member=%s",
        action_type,
        board_id,
        card_id,
        member,
    )

    published = await pubsub.push_trello_updated(body)
    return {"status": "ok", "action_type": action_type, "published": published}
