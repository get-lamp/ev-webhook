import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from webhook import setup

logger = logging.getLogger("workshop")


@asynccontextmanager
async def lifespan(app_: FastAPI):
    setup.routing(app_)
    await setup.watch()
    yield


app = FastAPI(
    title="Workshop API",
    version="0.1.0",
    lifespan=lifespan,
)
