from pydantic import BaseModel, ConfigDict


class TrelloBoard(BaseModel):
    """Board reference inside a Trello action."""
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None


class TrelloCard(BaseModel):
    """Card reference inside a Trello action."""
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None


class TrelloActionData(BaseModel):
    """The ``data`` block of a Trello action."""
    model_config = ConfigDict(extra="ignore")

    board: TrelloBoard | None = None
    card: TrelloCard | None = None


class TrelloMember(BaseModel):
    """Member reference inside a Trello action."""
    model_config = ConfigDict(extra="ignore")

    id: str
    username: str | None = None


class TrelloAction(BaseModel):
    """An action (event) inside a Trello webhook payload."""
    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    data: TrelloActionData | None = None
    memberCreator: TrelloMember | None = None


class TrelloModel(BaseModel):
    """The ``model`` block of a Trello webhook payload (board/card/list)."""
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str | None = None


class DashboardBoard(BaseModel):
    """Board reference used in dashboard registration."""
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str


class TrelloRegisterRequest(BaseModel):
    """``POST /trello/register`` request body."""
    name: str
    board: DashboardBoard


class TrelloWebhookPayload(BaseModel):
    """Incoming Trello webhook body.

    Relaxed schema — unknown fields are ignored. Documents the shape
    rather than enforcing it.
    """
    model_config = ConfigDict(extra="ignore")

    action: TrelloAction | None = None
    model: TrelloModel | None = None
