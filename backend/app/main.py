from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title="TechAtlas API",
    description="Australian tech job market intelligence API.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}
