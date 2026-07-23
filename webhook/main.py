import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from webhook import setup
import asyncio

logger = logging.getLogger("workshop")
logger.setLevel(logging.INFO)


async def _setup_watches() -> None:
    await asyncio.sleep(0.5)
    await setup.drive_watch()
    await setup.trello_watch()


@asynccontextmanager
async def lifespan(app_: FastAPI):
    setup.routing(app_)
    asyncio.create_task(_setup_watches())  # noqa
    yield


app = FastAPI(
    title="Workshop API",
    version="0.1.0",
    lifespan=lifespan,
)
