"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import APP_VERSION, router
from app.core.config import Settings, get_settings
from app.core.errors import ElexonResponseError, ElexonUpstreamError, InvalidDateRangeError, NoDataError
from app.core.logging import configure_logging
from app.services.analysis_service import AnalysisService
from app.services.elexon_client import ElexonClient

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, client: ElexonClient | None = None) -> FastAPI:
    """App factory. Tests inject a settings object and a client wired to a fake Elexon."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        elexon_client = client or ElexonClient(settings)
        app.state.analysis_service = AnalysisService(settings, elexon_client)
        yield
        await elexon_client.aclose()

    app = FastAPI(
        title="Wind Forecast Accuracy API",
        description="Elexon wind forecast vs actual, using the forecast available at day-ahead decision time.",
        version=APP_VERSION,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.exception_handler(InvalidDateRangeError)
    async def invalid_range_handler(_: Request, exc: InvalidDateRangeError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(NoDataError)
    async def no_data_handler(_: Request, exc: NoDataError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ElexonUpstreamError)
    async def upstream_handler(_: Request, exc: ElexonUpstreamError) -> JSONResponse:
        logger.error("Elexon upstream failure: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "The Elexon data service is unavailable or returned an error. Please retry shortly."},
        )

    @app.exception_handler(ElexonResponseError)
    async def bad_response_handler(_: Request, exc: ElexonResponseError) -> JSONResponse:
        logger.error("Unexpected Elexon response: %s", exc)
        return JSONResponse(
            status_code=502, content={"detail": "The Elexon data service returned data in an unexpected format."}
        )

    app.include_router(router)
    return app


app = create_app()
