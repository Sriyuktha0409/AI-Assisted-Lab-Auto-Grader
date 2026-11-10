from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import DEFAULT_SECRET, get_settings
from .database import Base, engine
from .routers import assignments, auth, submissions


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.environment == "production":
        if settings.secret_key == DEFAULT_SECRET:
            raise RuntimeError("SECRET_KEY must be set in production")
        if settings.sandbox_mode != "docker":
            raise RuntimeError("SANDBOX_MODE must be 'docker' in production")
    Base.metadata.create_all(engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Lab Auto-Grader", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(assignments.router)
    app.include_router(submissions.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
