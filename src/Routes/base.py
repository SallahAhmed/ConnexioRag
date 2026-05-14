from fastapi import APIRouter, Depends
from helpers.config import get_settings, Settings
import logging

logger = logging.getLogger(__name__)

base_router = APIRouter(
    prefix ="/api/v1",
    tags=["api_v1"]
)

@base_router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):

    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION

    return {
        "app_name": app_name,
        "app_version": app_version,
    }


@base_router.get("/health", tags=["health"])
async def health_check(app_settings: Settings = Depends(get_settings)):
    return {
        "status": "healthy",
        "service": "ConnexiosRAG",
        "version": app_settings.APP_VERSION,
    }
