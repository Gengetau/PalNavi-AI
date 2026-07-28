"""PalNavi AI local FastAPI application."""

from fastapi import FastAPI

from palnavi import __version__
from palnavi.api.routes import router

app = FastAPI(
    title="PalNavi AI",
    summary="Deterministic local API for PalNavi AI",
    version=__version__,
)
app.include_router(router)
