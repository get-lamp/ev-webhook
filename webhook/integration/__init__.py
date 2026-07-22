import sys

from webhook.config import settings

if settings.ENVIRONMENT == "local":
    from webhook.integration import localdrive, nats_pubsub, localwatch  # noqa: E402

    sys.modules["webhook.integration.drive"] = localdrive
    sys.modules["webhook.integration.pubsub"] = nats_pubsub
    sys.modules["webhook.integration.watch"] = localwatch
