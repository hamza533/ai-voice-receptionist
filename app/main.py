"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    agent,
    dashboard,
    integrations_api,
    public,
    settings_api,
    sms_api,
    waitlist_api,
)
from app.config import get_settings
from app.logging_setup import configure_logging, request_id_var

log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    worker = None
    if settings.worker_mode == "embedded":
        from app.jobs.worker import start_embedded

        worker = start_embedded(settings)
    log.info(
        "api started",
        extra={
            "version": __version__,
            "worker_mode": settings.worker_mode,
            "demo_mode": settings.demo_mode,
        },
    )
    yield
    if worker is not None:
        worker.stop()
        thread = getattr(worker, "_thread", None)
        if thread is not None:
            thread.join(timeout=25)  # let the in-flight job finish
    log.info("api stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.05, send_default_pii=False)

    app = FastAPI(
        title="AI Voice Receptionist API",
        version=__version__,
        description="Business config, agent tools, call records and dashboard API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid[:64])
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path not in {"/health", "/ready"}:
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "ms": ms,
                    "request_id": rid,
                },
            )
        return response

    app.include_router(public.router)
    app.include_router(dashboard.router)
    app.include_router(settings_api.router)
    app.include_router(agent.router)
    app.include_router(waitlist_api.router)
    app.include_router(sms_api.router)
    app.include_router(integrations_api.router)
    return app


app = create_app()
