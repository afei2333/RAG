from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import documents, health, query
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import init_db


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Local-first RAG service with Ollama and cloud model support.",
    )

    app.include_router(health.router)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse("app/static/index.html")

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()
