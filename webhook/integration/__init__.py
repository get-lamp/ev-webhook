import importlib
import sys

from webhook.config import settings

if settings.ENVIRONMENT == "local":
    localdrive = importlib.import_module("webhook.integration.drive.localdrive")
    nats_pubsub = importlib.import_module("webhook.integration.pubsub.nats_pubsub")
    localwatch = importlib.import_module("webhook.integration.watch.localwatch")

    sys.modules["webhook.integration.drive"] = localdrive
    sys.modules["webhook.integration.pubsub"] = nats_pubsub
    sys.modules["webhook.integration.watch"] = localwatch

    # importlib sets parent-package __dict__ entries that outlive the
    # sys.modules swap above.  Replace those too so that ``from
    # webhook.integration import drive`` resolves the swapped module.
    _self = sys.modules[__name__]
    _self.drive = localdrive
    _self.pubsub = nats_pubsub
    _self.watch = localwatch
