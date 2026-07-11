"""PalNavi AI local FastAPI application."""

from fastapi import FastAPI

from palnavi.api.routes import router

app = FastAPI(
    title="PalNavi AI",
    summary="Deterministic foundation API for PalNavi AI",
    version="0.1.0",
)
app.include_router(router)
