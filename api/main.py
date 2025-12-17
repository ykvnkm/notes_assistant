import os

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .db import ensure_table_exists
from .routes import router


def create_app() -> FastAPI:
    load_dotenv()  # подтягиваем .env на старте
    app = FastAPI(title="Notes Assistant API")
    # Разрешаем CORS для локального теста UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _init_db():
        ensure_table_exists()

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "student": os.getenv("STUDENT_NAME", ""),
            "services": {
                "postgres_host": os.getenv("POSTGRES_HOST", ""),
                "mongo_host": os.getenv("MONGO_HOST", ""),
                "redis_host": os.getenv("REDIS_HOST", ""),
                "qdrant_host": os.getenv("QDRANT_HOST", ""),
                "neo4j_host": os.getenv("NEO4J_HOST", ""),
                "rabbitmq_host": os.getenv("RABBITMQ_HOST", ""),
            },
        }

    @app.get("/ping")
    def ping():
        return {"message": "pong"}

    # Статика с веб-обёрткой (берём абсолютный путь, чтобы не зависеть от cwd)
    web_dir = Path(__file__).resolve().parent.parent / "web"
    app.mount("/web", StaticFiles(directory=web_dir, html=True), name="web")

    @app.get("/")
    def index():
        return RedirectResponse(url="/web/")

    app.include_router(router)

    return app


app = create_app()
