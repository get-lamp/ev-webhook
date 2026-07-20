import sys

from webhook.config import settings

if settings.ENVIRONMENT == "local":
    from webhook.integration import localdrive, localwatch  # noqa: E402

    sys.modules["webhook.integration.drive"] = localdrive
    sys.modules["webhook.integration.watch"] = localwatch
