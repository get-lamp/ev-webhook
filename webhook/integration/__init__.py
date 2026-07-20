import sys

from webhook.config import settings

if settings.ENVIRONMENT == "local":
    from webhook.integration import localdrive, localpubsub, localwatch  # noqa: E402

    sys.modules["webhook.integration.drive"] = localdrive
    sys.modules["webhook.integration.pubsub"] = localpubsub
    sys.modules["webhook.integration.watch"] = localwatch
