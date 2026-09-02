from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import documents, health
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Distributed document-processing backend with async jobs and progress tracking.",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(documents.router, prefix="/api/v1")
